"""MedGuard AI — FastAPI Application Entry Point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_config
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    config = get_config()
    config.load()
    setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    logger.info("MedGuard AI starting up...")
    logger.info(f"Database path: {os.getenv('DATABASE_PATH', 'data/medguard.db')}")
    yield
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


@app.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "medguard-ai",
        "version": "0.1.0",
    }
