"""Database engine and session management."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import Base
from src.utils.logger import get_logger

logger = get_logger(__name__)

_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        db_path = os.getenv("DATABASE_PATH", "data/medguard.db")
        if db_path == ":memory:":
            url = "sqlite:///:memory:"
            # StaticPool ensures all connections share the same :memory: DB
            _engine = create_engine(
                url,
                echo=False,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{db_path}"
            _engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})

        # Enable WAL mode for better concurrent read performance
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")  # Safe with WAL, 2-3x faster
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB page cache
            cursor.execute("PRAGMA busy_timeout=5000")  # 5s retry on lock
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()

        logger.info("Database engine initialized")
    return _engine


def get_session_factory():
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal


def get_session() -> Session:
    """Create a new database session."""
    factory = get_session_factory()
    return factory()


def init_db():
    """Create all tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def reset_engine():
    """Reset engine and session factory (for testing)."""
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
