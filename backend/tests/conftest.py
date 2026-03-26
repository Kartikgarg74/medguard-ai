"""Shared test fixtures for MedGuard AI."""

import os
import pytest

# Set test environment before any imports
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["MEDGUARD_ENCRYPTION_KEY"] = "test-key-for-testing-only"
os.environ["LOG_LEVEL"] = "WARNING"


@pytest.fixture
def config():
    """Provide test configuration."""
    return {
        "database": {"path": ":memory:", "echo": False},
        "ai": {
            "provider": "groq",
            "groq": {"api_key": "test-key", "daily_limit": 100},
        },
        "scraper": {"headless": True, "max_concurrent": 1},
        "compliance": {
            "wpi_factor": 1.0174028,
            "non_scheduled_max_increase": 0.10,
            "interest_rate": 0.15,
            "tolerance_pct": 0.02,
        },
    }
