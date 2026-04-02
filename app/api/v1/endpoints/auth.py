from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.schemas import (
    RegisterRequest, LoginRequest, RefreshRequest,
    TokenResponse, UserResponse, TenantResponse,
)
from app.services.auth_service import AuthService
from app.api.v1.dependencies.auth import CurrentUser

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    result  = await service.register(body)
    return {
        "success": True,
        "data": {
            "tenant": TenantResponse.model_validate(result["tenant"]),
            "user":   UserResponse.model_validate(result["user"]),
            "tokens": result["tokens"],
        },
    }


@router.post("/login")
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    result  = await service.login(body.email, body.password, body.tenant_slug)
    return {
        "success": True,
        "data": {
            "user":   UserResponse.model_validate(result["user"]),
            "tokens": result["tokens"],
        },
    }


@router.post("/refresh")
async def refresh_tokens(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    result  = await service.refresh(body.refresh_token)
    return {"success": True, "data": {"tokens": result["tokens"]}}


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.logout(body.refresh_token)


@router.get("/me")
async def get_me(current_user: CurrentUser):
    return {"success": True, "data": UserResponse.model_validate(current_user)}
