# Python FastAPI SaaS Backend

Production-ready multi-tenant SaaS API built with **FastAPI**, **async SQLAlchemy**, **PostgreSQL**, **JWT auth** with refresh token rotation, and **Stripe** billing. Full tenant isolation, RBAC, and webhook handling.

## Architecture

```
app/
├── main.py                          # FastAPI app factory, lifespan, middleware, error handlers
├── core/
│   ├── config.py                    # Pydantic Settings — environment validation
│   └── security.py                  # JWT encode/decode, bcrypt hashing
├── db/
│   └── session.py                   # Async SQLAlchemy engine, session factory, Base
├── models/
│   └── models.py                    # Tenant, User, RefreshToken, Subscription (SQLAlchemy mapped)
├── schemas/
│   └── schemas.py                   # Pydantic v2 request/response schemas with validators
├── services/
│   └── auth_service.py              # Register, login, token rotation, logout logic
└── api/v1/
    ├── dependencies/
    │   └── auth.py                  # CurrentUser, CurrentTenant, OwnerOrAdmin dependencies
    └── endpoints/
        ├── auth.py                  # Register, login, refresh, logout, /me
        ├── users.py                 # CRUD users with pagination and role checks
        └── billing.py              # Stripe checkout, portal, subscription, webhook handler
```

## Stack

- **Framework**: FastAPI 0.111 with async from the ground up
- **ORM**: SQLAlchemy 2.0 (async mode) + asyncpg driver
- **Validation**: Pydantic v2 with custom field validators
- **Auth**: JOSE JWT + passlib bcrypt, refresh token rotation stored as SHA-256 hash
- **Billing**: Stripe Checkout, Customer Portal, webhook handler for subscription lifecycle
- **Config**: pydantic-settings with `.env` file support

## API Endpoints

### Auth (rate limit: 10 req/15min recommended)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register tenant + owner, returns tokens |
| POST | `/api/v1/auth/login` | Login with tenant slug |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| GET  | `/api/v1/auth/me` | Current user |

### Users (Owner/Admin only)
| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/v1/users` | Paginated user list |
| GET    | `/api/v1/users/{id}` | Get user |
| POST   | `/api/v1/users` | Invite user |
| PATCH  | `/api/v1/users/{id}/role` | Update role |
| DELETE | `/api/v1/users/{id}` | Deactivate user |

### Billing
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/billing/checkout` | Create Stripe Checkout session |
| POST | `/api/v1/billing/portal` | Create Stripe Customer Portal session |
| GET  | `/api/v1/billing/subscription` | Current subscription |
| POST | `/api/v1/billing/webhook` | Stripe webhook handler |

## Response Format

```json
// Success
{ "success": true, "data": { ... } }

// Paginated
{ "items": [...], "total": 45, "page": 1, "per_page": 20, "pages": 3 }

// Error
{ "success": false, "code": "VALIDATION_ERROR", "message": "...", "details": [{ "field": "email", "message": "..." }] }
```

## Setup

```bash
# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy env
cp .env.example .env

# Start PostgreSQL + Redis
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16-alpine
docker run -d -p 6379:6379 redis:7-alpine

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload

# API docs
open http://localhost:8000/docs
```

## Security Design

- Passwords: bcrypt (passlib, cost factor auto)
- Refresh tokens: stored as SHA-256 hash, rotated on every use (token rotation attack detection)
- JWT: short-lived access tokens (30 min), long-lived refresh tokens (7 days)
- Tenant isolation: every query scoped by `tenant_id` — structurally enforced in services and dependencies
- Stripe webhooks: signature verified with `stripe.Webhook.construct_event` before processing

## Roles

| Role | Access |
|------|--------|
| `owner` | Full access, cannot be deactivated |
| `admin` | User management, full resource write |
| `member` | Standard access |
| `viewer` | Read-only |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async connection string |
| `SECRET_KEY` | JWT signing key (min 32 chars) |
| `STRIPE_SECRET_KEY` | Stripe API key |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret |
| `STRIPE_PRICE_STARTER/PRO/ENTERPRISE` | Stripe price IDs |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Default: 30 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Default: 7 |

## Why This Over Other FastAPI Boilerplates?

| Feature | This Boilerplate | Typical FastAPI Starters |
|---|---|---|
| Demo mode (SQLite, zero config) | ✅ Auto-seeded, instant start | ❌ Requires PostgreSQL setup |
| Multi-tenancy | ✅ Tenant-scoped data isolation | ❌ Single-tenant |
| Stripe billing | ✅ Checkout, webhooks, portal | ❌ Not included |
| JWT + refresh tokens | ✅ Rotation, revocation, expiry | ⚠️ Basic JWT only |
| RBAC | ✅ Admin, member, viewer roles | ⚠️ No role system |
| Async SQLAlchemy | ✅ Full async with connection pooling | ⚠️ Often sync |
| API versioning | ✅ /api/v1/ prefix built in | ❌ Flat routes |
