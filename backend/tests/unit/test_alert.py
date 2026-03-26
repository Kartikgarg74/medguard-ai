"""Tests for alert agent — severity routing, deduplication, HMAC signing."""

import os
import uuid

import pytest

os.environ["DATABASE_PATH"] = ":memory:"

from src.agents.alert.agent import ALERT_ROUTING, AlertAgent
from src.agents.alert.telegram import sign_callback_data, verify_callback_data
from src.database.models import Alert, ComplianceCheck, Medicine
from src.database.session import get_session, init_db, reset_engine


@pytest.fixture(autouse=True)
def fresh_db():
    reset_engine()
    os.environ["DATABASE_PATH"] = ":memory:"
    init_db()
    yield
    reset_engine()


# --- HMAC Signing ---


def test_sign_and_verify():
    signed = sign_callback_data("ack:12345")
    verified = verify_callback_data(signed)
    assert verified == "ack:12345"


def test_verify_tampered_data():
    signed = sign_callback_data("ack:12345")
    tampered = signed[:-1] + "X"
    assert verify_callback_data(tampered) is None


def test_verify_no_separator():
    assert verify_callback_data("noseparator") is None


# --- Alert Routing ---


def test_critical_routes_to_telegram():
    assert "telegram_immediate" in ALERT_ROUTING["critical"]


def test_high_routes_to_telegram():
    assert "telegram_immediate" in ALERT_ROUTING["high"]


def test_low_routes_to_log_only():
    assert "log_only" in ALERT_ROUTING["low"]


# --- Deduplication ---


def test_dedup_first_alert_not_duplicate():
    agent = AlertAgent()
    assert agent._is_duplicate("check-1") is False


def test_dedup_second_alert_is_duplicate():
    agent = AlertAgent()
    agent._mark_alerted("check-1")
    assert agent._is_duplicate("check-1") is True


def test_dedup_different_check_not_duplicate():
    agent = AlertAgent()
    agent._mark_alerted("check-1")
    assert agent._is_duplicate("check-2") is False


# --- Alert Format ---


def test_format_alert_message():
    agent = AlertAgent()

    class MockCheck:
        severity = "critical"
        platform = "1mg"
        retail_price = 45.0
        ceiling_price = 25.0
        overcharge_amount = 20.0
        overcharge_pct = 80.0
        dpco_rule_applied = "Para 4-7, 15"

    msg = agent._format_alert(MockCheck(), "Paracetamol 500mg")
    assert "CRITICAL" in msg
    assert "Paracetamol" in msg
    assert "1mg" in msg
    assert "20.00" in msg
    assert "80.0%" in msg


# --- Alert Agent Execute (without Telegram) ---


@pytest.mark.asyncio
async def test_alert_agent_no_violations():
    agent = AlertAgent(telegram_bot=None)
    result = await agent.execute(severity_threshold="high")
    assert result["processed"] == 0
    assert result["alerted"] == 0


@pytest.mark.asyncio
async def test_alert_agent_with_violations():
    session = get_session()

    med_id = str(uuid.uuid4())
    session.add(Medicine(id=med_id, name="TestDrug", salt_composition="Test"))

    check_id = str(uuid.uuid4())
    session.add(
        ComplianceCheck(
            id=check_id,
            medicine_id=med_id,
            platform="1mg",
            ceiling_price=25.0,
            retail_price=50.0,
            overcharge_amount=25.0,
            overcharge_pct=100.0,
            status="violation",
            severity="critical",
            dpco_rule_applied="Para 4-7",
            confidence_score=1.0,
            checked_by="rule_engine",
        )
    )
    session.commit()
    session.close()

    agent = AlertAgent(telegram_bot=None)
    result = await agent.execute(severity_threshold="critical")
    assert result["processed"] >= 1
    assert result["alerted"] >= 1

    # Check alert was saved to DB
    session = get_session()
    alerts = session.query(Alert).all()
    assert len(alerts) >= 1
    assert alerts[0].severity == "critical"
    session.close()


@pytest.mark.asyncio
async def test_alert_agent_respects_threshold():
    """Low severity should not alert when threshold is 'high'."""
    session = get_session()

    med_id = str(uuid.uuid4())
    session.add(Medicine(id=med_id, name="TestDrug2", salt_composition="Test2"))
    session.add(
        ComplianceCheck(
            id=str(uuid.uuid4()),
            medicine_id=med_id,
            platform="netmeds",
            ceiling_price=100.0,
            retail_price=103.0,
            overcharge_amount=3.0,
            overcharge_pct=3.0,
            status="violation",
            severity="low",
            confidence_score=1.0,
            checked_by="rule_engine",
        )
    )
    session.commit()
    session.close()

    agent = AlertAgent(telegram_bot=None)
    result = await agent.execute(severity_threshold="high")
    # Low severity should not be processed when threshold is "high"
    assert result["alerted"] == 0
