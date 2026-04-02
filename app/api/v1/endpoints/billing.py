from fastapi import APIRouter, HTTPException, Request, Header
from sqlalchemy import select
import stripe

from app.core.config import settings
from app.models.models import Tenant, Subscription, Plan, SubscriptionStatus
from app.schemas.schemas import CheckoutRequest, CheckoutResponse, BillingPortalResponse, SubscriptionResponse
from app.api.v1.dependencies.auth import CurrentUser, CurrentTenant, DB

stripe.api_key = settings.stripe_secret_key

PLAN_PRICE_MAP = {
    Plan.STARTER:    settings.stripe_price_starter,
    Plan.PRO:        settings.stripe_price_pro,
    Plan.ENTERPRISE: settings.stripe_price_enterprise,
}

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(body: CheckoutRequest, db: DB, current_user: CurrentUser, tenant: CurrentTenant):
    if body.plan == Plan.FREE:
        raise HTTPException(status_code=400, detail="Cannot checkout free plan")

    price_id = PLAN_PRICE_MAP.get(body.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Price not configured for this plan")

    # Create or retrieve Stripe customer
    if not tenant.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=tenant.name,
            metadata={"tenant_id": str(tenant.id), "tenant_slug": tenant.slug},
        )
        tenant.stripe_customer_id = customer.id

    session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=body.success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=body.cancel_url,
        metadata={"tenant_id": str(tenant.id), "plan": body.plan.value},
        subscription_data={"trial_period_days": 14 if tenant.plan == Plan.FREE else None},
    )

    return CheckoutResponse(checkout_url=session.url or "", session_id=session.id)


@router.post("/portal", response_model=BillingPortalResponse)
async def create_billing_portal(db: DB, current_user: CurrentUser, tenant: CurrentTenant, return_url: str = ""):
    if not tenant.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=return_url or "https://app.example.com/settings/billing",
    )
    return BillingPortalResponse(portal_url=session.url)


@router.get("/subscription", response_model=SubscriptionResponse | None)
async def get_subscription(db: DB, tenant: CurrentTenant):
    sub = await db.scalar(
        select(Subscription)
        .where(Subscription.tenant_id == tenant.id)
        .order_by(Subscription.created_at.desc())
    )
    if not sub:
        return None
    return SubscriptionResponse.model_validate(sub)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: DB, stripe_signature: str = Header(alias="stripe-signature")):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data        = event["data"]["object"]

    if event_type == "customer.subscription.created":
        await _handle_subscription_created(db, data)
    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        await _handle_subscription_updated(db, data)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(db, data)

    return {"received": True}


async def _handle_subscription_created(db: DB, data: dict) -> None:
    tenant = await db.scalar(select(Tenant).where(Tenant.stripe_customer_id == data["customer"]))
    if not tenant:
        return

    plan = _price_to_plan(data["items"]["data"][0]["price"]["id"])
    from datetime import datetime, timezone
    sub = Subscription(
        tenant_id=tenant.id,
        stripe_subscription_id=data["id"],
        stripe_price_id=data["items"]["data"][0]["price"]["id"],
        plan=plan,
        status=SubscriptionStatus(data["status"]),
        current_period_start=datetime.fromtimestamp(data["current_period_start"], tz=timezone.utc),
        current_period_end=datetime.fromtimestamp(data["current_period_end"], tz=timezone.utc),
        cancel_at_period_end=data.get("cancel_at_period_end", False),
    )
    db.add(sub)
    tenant.plan = plan


async def _handle_subscription_updated(db: DB, data: dict) -> None:
    sub = await db.scalar(
        select(Subscription).where(Subscription.stripe_subscription_id == data["id"])
    )
    if not sub:
        return

    from datetime import datetime, timezone
    sub.status = SubscriptionStatus(data["status"])
    sub.cancel_at_period_end = data.get("cancel_at_period_end", False)
    sub.current_period_end = datetime.fromtimestamp(data["current_period_end"], tz=timezone.utc)

    if data["status"] == "canceled":
        from datetime import datetime, timezone
        sub.canceled_at = datetime.now(timezone.utc)
        sub.tenant.plan = Plan.FREE


async def _handle_payment_failed(db: DB, data: dict) -> None:
    tenant = await db.scalar(select(Tenant).where(Tenant.stripe_customer_id == data["customer"]))
    if tenant:
        sub = await db.scalar(
            select(Subscription).where(Subscription.tenant_id == tenant.id)
            .order_by(Subscription.created_at.desc())
        )
        if sub:
            sub.status = SubscriptionStatus.PAST_DUE


def _price_to_plan(price_id: str) -> Plan:
    for plan, pid in PLAN_PRICE_MAP.items():
        if pid == price_id:
            return plan
    return Plan.STARTER
