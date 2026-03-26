"""Tests for immutable SHA-256 chained audit log."""

import os

import pytest

os.environ["DATABASE_PATH"] = ":memory:"

from src.database.session import init_db, reset_engine
from src.security.audit_log import (
    GENESIS_HASH,
    log_audit,
    verify_chain,
    get_audit_stats,
    _compute_hash,
    _hash_data,
)


@pytest.fixture(autouse=True)
def fresh_db():
    reset_engine()
    os.environ["DATABASE_PATH"] = ":memory:"
    init_db()
    yield
    reset_engine()


def test_compute_hash_deterministic():
    h1 = _compute_hash("hello")
    h2 = _compute_hash("hello")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_hash_differs():
    assert _compute_hash("hello") != _compute_hash("world")


def test_hash_data_handles_none():
    h = _hash_data(None)
    assert len(h) == 64


def test_hash_data_handles_dict():
    h = _hash_data({"key": "value"})
    assert len(h) == 64


def test_log_audit_creates_entry():
    entry_id = log_audit(
        agent_name="test_agent",
        action="test.action",
        resource_type="medicine",
        resource_id="med-123",
        input_data={"drug": "Paracetamol"},
        output_data={"status": "compliant"},
    )
    assert entry_id is not None
    assert len(entry_id) == 36  # UUID


def test_log_audit_genesis_hash():
    """First entry should have prev_hash = GENESIS_HASH."""
    from src.database.session import get_session
    from src.database.models import AuditLog

    log_audit(agent_name="test", action="first")

    session = get_session()
    entry = session.query(AuditLog).first()
    assert entry.prev_hash == GENESIS_HASH
    assert entry.sequence_num == 1
    session.close()


def test_log_audit_chain_linking():
    """Second entry's prev_hash should equal first entry's entry_hash."""
    from src.database.session import get_session
    from src.database.models import AuditLog

    log_audit(agent_name="test", action="first")
    log_audit(agent_name="test", action="second")

    session = get_session()
    entries = session.query(AuditLog).order_by(AuditLog.sequence_num).all()
    assert len(entries) == 2
    assert entries[1].prev_hash == entries[0].entry_hash
    assert entries[1].sequence_num == 2
    session.close()


def test_verify_chain_empty():
    result = verify_chain()
    assert result["valid"] is True
    assert result["total_entries"] == 0


def test_verify_chain_single_entry():
    log_audit(agent_name="test", action="solo")
    result = verify_chain()
    assert result["valid"] is True
    assert result["total_entries"] == 1


def test_verify_chain_multiple_entries():
    for i in range(5):
        log_audit(agent_name="test", action=f"action_{i}")

    result = verify_chain()
    assert result["valid"] is True
    assert result["total_entries"] == 5


def test_verify_chain_detects_tampering():
    """Modifying an entry should break chain verification."""
    from src.database.session import get_session
    from src.database.models import AuditLog

    log_audit(agent_name="test", action="first")
    log_audit(agent_name="test", action="second")
    log_audit(agent_name="test", action="third")

    # Tamper with the second entry
    session = get_session()
    entry = session.query(AuditLog).filter_by(sequence_num=2).first()
    entry.action = "TAMPERED"
    session.commit()
    session.close()

    result = verify_chain()
    assert result["valid"] is False
    assert result["first_broken_at"] == 2


def test_get_audit_stats():
    log_audit(agent_name="scraper", action="scrape.1mg")
    log_audit(agent_name="scraper", action="scrape.nppa")
    log_audit(agent_name="compliance", action="check.run")

    stats = get_audit_stats()
    assert stats["total_entries"] == 3
    assert stats["by_agent"]["scraper"] == 2
    assert stats["by_agent"]["compliance"] == 1


def test_log_audit_with_llm_metadata():
    entry_id = log_audit(
        agent_name="compliance",
        action="check.edge_case",
        llm_model="llama-3.1-8b-instant",
        llm_tokens_used=350,
        llm_cost_usd=0.0001,
        duration_ms=245,
    )
    assert entry_id is not None
