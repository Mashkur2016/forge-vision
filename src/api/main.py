"""
FastAPI application entry point for FORGE-Vision.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api.limiter import limiter
from src.api.routes import account as account_router
from src.api.routes import analytics as analytics_router
from src.api.routes import audit as audit_router
from src.api.routes import auth as auth_router
from src.api.routes import continual as continual_router
from src.api.routes import feedback as feedback_router
from src.api.routes import health as health_router
from src.api.routes import leaderboard as leaderboard_router
from src.api.routes import live_ws as live_ws_router
from src.api.routes import llm_sop_parser as llm_sop_parser_router
from src.api.routes import notifications as notifications_router
from src.api.routes import reports as reports_router
from src.api.routes import session as session_router
from src.api.routes import settings as settings_router
from src.api.routes import sops as sops_router
from src.api.routes import users as admin_users_router
from src.api.routes import worker as worker_router
from src.config import settings as app_settings
from src.database.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — validate production secrets
    if app_settings.ENVIRONMENT == "production":
        if app_settings.JWT_SECRET_KEY == "dev-secret-change-in-production":
            raise RuntimeError("JWT_SECRET_KEY must be changed before production deployment")
        if not getattr(app_settings, "SETTINGS_ENCRYPTION_KEY", None):
            raise RuntimeError("SETTINGS_ENCRYPTION_KEY must be set in production")
    await create_tables()
    # Pre-warm the live-camera CV models in the background so the first
    # WebSocket connection is fast (and never blocks the event loop).
    import asyncio as _asyncio

    from src.api.routes.live_ws import warm_models
    _asyncio.create_task(warm_models())
    yield
    # Shutdown (nothing to clean up yet)


app = FastAPI(
    title="FORGE-Vision API",
    description="Hybrid CV + GenAI Employee Training System",
    version="0.1.0",
    lifespan=lifespan,
    # Disable interactive docs in production
    docs_url="/docs" if app_settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if app_settings.ENVIRONMENT != "production" else None,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── Middleware ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        app_settings.API_BASE_URL,
        "http://localhost:8501",
        "https://localhost:8501",  # Streamlit (HTTPS)
        "http://localhost:5173",
        "https://localhost:5173",
        "http://localhost:5174",
        "https://localhost:5174",
        "http://localhost:5175",
        "https://localhost:5175",
        "http://localhost:5176",
        "https://localhost:5176",  # React dev server (Vite HTTPS — port varies)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
)

if app_settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=app_settings.ALLOWED_HOSTS.split(","),
    )

# ── Security headers ───────────────────────────────────────────────────────

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if app_settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ── Routers ────────────────────────────────────────────────────────────────

app.include_router(auth_router.router)
app.include_router(settings_router.open_router)   # /active-provider — all auth roles
app.include_router(settings_router.router)         # admin-only settings management
app.include_router(session_router.router)
app.include_router(feedback_router.router)
app.include_router(analytics_router.router)
app.include_router(worker_router.router)

# Phase 4+ extended endpoints for the Streamlit UI
app.include_router(llm_sop_parser_router.router)
app.include_router(notifications_router.router)
app.include_router(audit_router.router)
app.include_router(admin_users_router.router)
app.include_router(leaderboard_router.router)
app.include_router(reports_router.router)
app.include_router(sops_router.router)
app.include_router(account_router.router)
app.include_router(continual_router.router)   # Enhancement 5 — continual learning
app.include_router(live_ws_router.router)      # browser-webcam frame streaming (no TURN)
app.include_router(health_router.router)

# Audit logging middleware — installed AFTER routes so it sees the final status
app.middleware("http")(audit_router.audit_middleware)


# ── Health check ──────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "forge-vision-api"}
