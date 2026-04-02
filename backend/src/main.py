"""MedGuard AI — FastAPI Application Entry Point."""

import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.audit import router as audit_router
from src.api.dashboard import router as dashboard_router
from src.api.medicines import router as medicines_router
from src.api.reports import router as reports_router
from src.api.scraper_api import router as scraper_router
from src.api.violations import router as violations_router
from src.config import get_config
from src.database.session import init_db
from src.security.audit_log import log_audit, verify_chain
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    config = get_config()
    config.load()
    setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    logger.info("MedGuard AI starting up...")

    # Initialize database
    init_db()
    logger.info(f"Database initialized: {os.getenv('DATABASE_PATH', 'data/medguard.db')}")

    # Verify audit chain on startup
    chain_status = verify_chain()
    if chain_status["valid"]:
        logger.info(f"Audit chain verified: {chain_status['total_entries']} entries, integrity OK")
    else:
        logger.warning(f"Audit chain integrity BROKEN: {chain_status['error']}")

    log_audit(agent_name="system", action="startup")

    yield

    log_audit(agent_name="system", action="shutdown")
    logger.info("MedGuard AI shutting down...")


app = FastAPI(
    title="MedGuard AI",
    description="Multi-Agent Medicine Price Compliance System under DPCO 2013",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — configurable via environment
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
_cors_origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# --- Rate limiting middleware ---
_rate_limit_store: dict[str, list[datetime]] = defaultdict(list)
_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "100"))  # requests per minute
_RATE_WINDOW = timedelta(minutes=1)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple IP-based rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now()

    # Prune old entries
    _rate_limit_store[client_ip] = [
        ts for ts in _rate_limit_store[client_ip] if now - ts < _RATE_WINDOW
    ]

    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."},
        )

    _rate_limit_store[client_ip].append(now)
    return await call_next(request)


# Mount API routers
app.include_router(medicines_router)
app.include_router(violations_router)
app.include_router(dashboard_router)
app.include_router(reports_router)
app.include_router(scraper_router)
app.include_router(audit_router)


@app.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "medguard-ai",
        "version": "0.1.0",
    }
