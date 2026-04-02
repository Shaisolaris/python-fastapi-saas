import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.models.models import Tenant, User, RefreshToken, Plan, Role
from app.schemas.schemas import RegisterRequest, TokenResponse


class AuthService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, data: RegisterRequest) -> dict:
        # Check slug uniqueness
        slug_exists = await self.db.scalar(select(Tenant.id).where(Tenant.slug == data.tenant_slug))
        if slug_exists:
            raise HTTPException(status_code=409, detail="Tenant slug already taken")

        tenant = Tenant(
            name=data.tenant_name,
            slug=data.tenant_slug,
            plan=Plan.FREE,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        self.db.add(tenant)
        await self.db.flush()

        user = User(
            tenant_id=tenant.id,
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            role=Role.OWNER,
            is_verified=True,
        )
        self.db.add(user)
        await self.db.flush()

        tokens = await self._create_token_pair(user)

        return {"tenant": tenant, "user": user, "tokens": tokens}

    async def login(self, email: str, password: str, tenant_slug: str) -> dict:
        tenant = await self.db.scalar(
            select(Tenant).where(Tenant.slug == tenant_slug, Tenant.is_active.is_(True))
        )
        if not tenant:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user = await self.db.scalar(
            select(User).where(
                User.email == email,
                User.tenant_id == tenant.id,
                User.is_active.is_(True),
            )
        )
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user.last_login_at = datetime.now(timezone.utc)
        tokens = await self._create_token_pair(user)

        return {"user": user, "tokens": tokens}

    async def refresh(self, raw_token: str) -> dict:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        stored = await self.db.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .join(RefreshToken.user)
        )
        if not stored or not stored.is_valid:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        # Rotate: revoke old, issue new
        stored.revoked_at = datetime.now(timezone.utc)
        user = await self.db.get(User, stored.user_id)
        tokens = await self._create_token_pair(user)
        return {"tokens": tokens}

    async def logout(self, raw_token: str) -> None:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        stored = await self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        if stored:
            stored.revoked_at = datetime.now(timezone.utc)

    async def _create_token_pair(self, user: User) -> TokenResponse:
        access_token = create_access_token(
            str(user.id),
            extra_claims={"tenant_id": str(user.tenant_id), "role": user.role.value},
        )
        raw_refresh = secrets.token_hex(32)
        refresh_token = create_refresh_token(str(user.id))

        stored = RefreshToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_refresh.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        )
        self.db.add(stored)

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )
