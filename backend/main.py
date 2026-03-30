"""
FastAPI application entry point.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend.config import settings
from backend.database import init_db
from backend.middleware import RequestTimingMiddleware
from backend.routes import auth, admin, voting, reports

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

logger = logging.getLogger(__name__)

# ─── Rate limiter (shared across all routers) ─────────────────────────────────
# Per-IP, in-memory by default. Set REDIS_URL in .env to enable cross-worker
# rate limiting via Redis: limiter = Limiter(key_func=..., storage_uri=REDIS_URL)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Secure apartment voting system with WhatsApp OTP verification, "
        "anonymous & identified voting modes, and full auditability."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Expose limiter on app.state so slowapi decorators in routers can find it
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── Middleware stack (order matters: outermost added last) ───────────────────
app.add_middleware(RequestTimingMiddleware)      # request timing + access log
app.add_middleware(SlowAPIMiddleware)            # slowapi enforcement
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production to exact Streamlit origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(voting.router)
app.include_router(reports.router)


# ─── Lifecycle ───────────────────────────────────────────────────────────────
@app.on_event("startup")
async def _startup():
    logger.info("Initialising database …")
    init_db()
    logger.info("Database ready.")


# ─── Health & metrics ────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    """Minimal liveness probe for load balancers / Docker healthcheck."""
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/metrics", tags=["Health"])
async def metrics(request: Request):
    """
    Basic operational metrics.
    For production, replace with Prometheus exposition format via
    `prometheus-fastapi-instrumentator`.
    """
    from backend.database import SessionLocal
    from backend.models.user import User, UserStatus
    from backend.models.topic import Topic, TopicStatus
    from backend.models.vote import VoteTracking

    db = SessionLocal()
    try:
        eligible = db.query(User).filter(
            User.status == UserStatus.APPROVED,
            User.is_active.is_(True),
        ).count()
        total_votes = db.query(VoteTracking).count()
        active_topics = db.query(Topic).filter(
            Topic.status == TopicStatus.ACTIVE
        ).count()
    finally:
        db.close()

    return {
        "eligible_voters": eligible,
        "total_votes_cast": total_votes,
        "active_topics": active_topics,
        "participation_pct": round((total_votes / eligible * 100) if eligible else 0, 1),
    }
