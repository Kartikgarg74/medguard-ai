"""MedGuard AI — FastAPI Application Entry Point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
