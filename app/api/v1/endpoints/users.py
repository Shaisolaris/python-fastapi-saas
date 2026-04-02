from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func
from math import ceil

from app.db.session import get_db
from app.models.models import User, Role
from app.schemas.schemas import UserResponse, UserCreate, UserUpdate, RoleUpdate, PaginatedResponse
from app.core.security import hash_password
from app.api.v1.dependencies.auth import CurrentUser, OwnerOrAdmin, DB

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=PaginatedResponse)
async def list_users(
    db: DB,
    current_user: OwnerOrAdmin,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    tenant_id = current_user.tenant_id
    total = await db.scalar(select(func.count(User.id)).where(User.tenant_id == tenant_id))
    users = (await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )).scalars().all()

    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total or 0,
        page=page,
        per_page=per_page,
        pages=ceil((total or 0) / per_page),
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: DB, current_user: OwnerOrAdmin):
    import uuid
    user = await db.scalar(
        select(User).where(User.id == uuid.UUID(user_id), User.tenant_id == current_user.tenant_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.post("", status_code=201, response_model=UserResponse)
async def invite_user(body: UserCreate, db: DB, current_user: OwnerOrAdmin):
    existing = await db.scalar(
        select(User).where(User.email == body.email, User.tenant_id == current_user.tenant_id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    user = User(
        tenant_id=current_user.tenant_id,
        email=body.email,
        password_hash=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
    )
    db.add(user)
    await db.flush()
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_role(user_id: str, body: RoleUpdate, db: DB, current_user: OwnerOrAdmin):
    import uuid
    user = await db.scalar(
        select(User).where(User.id == uuid.UUID(user_id), User.tenant_id == current_user.tenant_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=422, detail="Cannot change your own role")
    if user.role == Role.OWNER:
        raise HTTPException(status_code=403, detail="Cannot change owner role")
    user.role = body.role
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(user_id: str, db: DB, current_user: OwnerOrAdmin):
    import uuid
    user = await db.scalar(
        select(User).where(User.id == uuid.UUID(user_id), User.tenant_id == current_user.tenant_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=422, detail="Cannot deactivate yourself")
    if user.role == Role.OWNER:
        raise HTTPException(status_code=403, detail="Cannot deactivate owner")
    user.is_active = False
    for token in user.refresh_tokens:
        from datetime import datetime, timezone
        token.revoked_at = datetime.now(timezone.utc)
