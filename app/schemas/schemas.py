from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, Field, field_validator
import re
from app.models.models import Plan, Role, SubscriptionStatus


# ─── Base ─────────────────────────────────────────────────────────────────────

class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=100)
    tenant_slug: str = Field(min_length=2, max_length=50)
    first_name:  str = Field(min_length=1, max_length=50)
    last_name:   str = Field(min_length=1, max_length=50)
    email:       EmailStr
    password:    str = Field(min_length=8)

    @field_validator("tenant_slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        return v


class LoginRequest(BaseModel):
    email:       EmailStr
    password:    str
    tenant_slug: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int


# ─── Tenant ───────────────────────────────────────────────────────────────────

class TenantResponse(TimestampMixin):
    id:       uuid.UUID
    name:     str
    slug:     str
    plan:     Plan
    is_active: bool
    trial_ends_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─── User ─────────────────────────────────────────────────────────────────────

class UserResponse(TimestampMixin):
    id:         uuid.UUID
    email:      str
    first_name: str
    last_name:  str
    full_name:  str
    role:       Role
    is_active:  bool
    is_verified: bool
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email:      EmailStr
    first_name: str = Field(min_length=1, max_length=50)
    last_name:  str = Field(min_length=1, max_length=50)
    password:   str = Field(min_length=8)
    role:       Role = Role.MEMBER


class UserUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=50)
    last_name:  str | None = Field(None, max_length=50)
    is_active:  bool | None = None


class RoleUpdate(BaseModel):
    role: Role


# ─── Subscription ──────────────────────────────────────────────────────────────

class SubscriptionResponse(BaseModel):
    id:                     uuid.UUID
    plan:                   Plan
    status:                 SubscriptionStatus
    current_period_start:   datetime
    current_period_end:     datetime
    cancel_at_period_end:   bool
    canceled_at:            datetime | None = None

    model_config = {"from_attributes": True}


class CheckoutRequest(BaseModel):
    plan:         Plan
    success_url:  str
    cancel_url:   str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id:   str


class BillingPortalResponse(BaseModel):
    portal_url: str


# ─── Pagination ──────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items:      list[Any]
    total:      int
    page:       int
    per_page:   int
    pages:      int


# ─── API Response wrapper ─────────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    data:    Any  = None
    message: str  = ""


class ErrorDetail(BaseModel):
    field:   str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    code:    str
    message: str
    details: list[ErrorDetail] = []
