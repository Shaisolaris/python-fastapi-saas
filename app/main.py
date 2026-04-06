import os
# Demo mode: runs with sample data when no API keys configured
DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true' or not os.getenv('DATABASE_URL')
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.db.session import init_db, close_db
from app.api.v1.endpoints import auth, users, billing
from app.core.rate_limiter import rate_limit_middleware
from starlette.middleware.base import BaseHTTPMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Production multi-tenant SaaS API — FastAPI, async SQLAlchemy, JWT auth, Stripe billing",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

    # Validation error handler — consistent JSON format
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(l) for l in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"success": False, "code": "VALIDATION_ERROR", "message": "Validation failed", "details": details},
        )

    # Generic error handler
    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception):
        if settings.debug:
            raise exc
        return JSONResponse(
            status_code=500,
            content={"success": False, "code": "INTERNAL_ERROR", "message": "Internal server error"},
        )

    # Routers
    prefix = "/api/v1"
    app.include_router(auth.router,    prefix=prefix)
    app.include_router(users.router,   prefix=prefix)
    app.include_router(billing.router, prefix=prefix)

    # Health check
    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    return app


app = create_app()
