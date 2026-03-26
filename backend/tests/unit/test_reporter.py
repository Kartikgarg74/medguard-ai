"""Tests for report generation."""

import os
import uuid

import pytest

os.environ["DATABASE_PATH"] = ":memory:"

from src.agents.reporter.generator import (
    render_daily_summary,
    render_violation_report,
)
from src.database.models import ComplianceCheck, Medicine
from src.database.session import get_session, init_db, reset_engine


@pytest.fixture(autouse=True)
def fresh_db():
    reset_engine()
    os.environ["DATABASE_PATH"] = ":memory:"
    init_db()
    yield
    reset_engine()


# --- Template Rendering Tests ---


def test_render_violation_report_basic():
    html = render_violation_report(
        period="2026-03-26",
        total_checked=100,
        total_violations=5,
        compliance_rate=95.0,
        violations=[
            {
                "medicine_name": "Paracetamol 500mg",
                "platform": "1mg",
                "retail_price": 45.00,
                "ceiling_price": 25.00,
                "overcharge_amount": 20.00,
                "overcharge_pct": 80.0,
                "severity": "critical",
                "dpco_rule": "Para 4-7, 15",
            }
        ],
        platform_stats={
            "1mg": {"checked": 50, "violations": 3, "compliance_rate": 94.0},
            "pharmeasy": {"checked": 50, "violations": 2, "compliance_rate": 96.0},
        },
    )
    assert "MedGuard AI" in html
    assert "Paracetamol" in html
    assert "95.0%" in html
    assert "CRITICAL" in html
    assert "Para 4-7" in html


def test_render_violation_report_empty():
    html = render_violation_report(
        period="2026-03-26",
        total_checked=0,
        total_violations=0,
        compliance_rate=100.0,
        violations=[],
        platform_stats={},
    )
    assert "MedGuard AI" in html
    assert "100.0%" in html


def test_render_violation_report_with_narrative():
    html = render_violation_report(
        period="2026-03-26",
        total_checked=50,
        total_violations=3,
        compliance_rate=94.0,
        violations=[],
        platform_stats={},
        narrative="<p>Analysis: 3 violations detected across 2 platforms.</p>",
    )
    assert "AI-Generated Analysis" in html
    assert "3 violations detected" in html


def test_render_daily_summary():
    html = render_daily_summary(
        date_str="2026-03-26",
        stats={
            "total_checked": 200,
            "violations": 10,
            "compliance_rate": 95.0,
        },
        top_violations=[
            {
                "medicine_name": "Metformin 500mg",
                "platform": "pharmeasy",
                "overcharge_amount": 15.50,
                "overcharge_pct": 45.0,
                "severity": "high",
            }
        ],
        platform_breakdown={
            "1mg": {"violations": 5, "avg_overcharge": 12.30},
            "pharmeasy": {"violations": 5, "avg_overcharge": 18.50},
        },
    )
    assert "Daily Summary" in html
    assert "Metformin" in html
    assert "HIGH" in html
    assert "200" in html


def test_render_daily_summary_no_violations():
    html = render_daily_summary(
        date_str="2026-03-26",
        stats={"total_checked": 100, "violations": 0, "compliance_rate": 100.0},
        top_violations=[],
        platform_breakdown={},
    )
    assert "100.0%" in html


# --- DB Integration for Reporter Stats ---


def _seed_compliance_data(session):
    """Seed test compliance data."""
    med_id = str(uuid.uuid4())
    med = Medicine(
        id=med_id,
        name="Paracetamol 500mg",
        salt_composition="Paracetamol",
        dpco_scheduled=True,
    )
    session.add(med)

    # 3 violations + 2 compliant
    for i, (status, severity, overcharge) in enumerate(
        [
            ("violation", "critical", 20.0),
            ("violation", "high", 10.0),
            ("violation", "medium", 5.0),
            ("compliant", None, 0.0),
            ("compliant", None, 0.0),
        ]
    ):
        cc = ComplianceCheck(
            id=str(uuid.uuid4()),
            medicine_id=med_id,
            platform="1mg" if i % 2 == 0 else "pharmeasy",
            ceiling_price=25.0,
            retail_price=25.0 + overcharge,
            overcharge_amount=overcharge,
            overcharge_pct=(overcharge / 25.0 * 100) if overcharge > 0 else 0,
            status=status,
            severity=severity,
            confidence_score=1.0,
            checked_by="rule_engine",
        )
        session.add(cc)
    session.commit()


def test_reporter_stats_query():
    """Test that reporter can query compliance stats correctly."""
    from sqlalchemy import func

    session = get_session()
    _seed_compliance_data(session)

    total = session.query(func.count(ComplianceCheck.id)).scalar()
    violations = (
        session.query(func.count(ComplianceCheck.id))
        .filter(ComplianceCheck.status == "violation")
        .scalar()
    )
    assert total == 5
    assert violations == 3
    session.close()


def test_reporter_platform_breakdown():
    session = get_session()
    _seed_compliance_data(session)

    from sqlalchemy import func

    platforms = (
        session.query(
            ComplianceCheck.platform,
            func.count(ComplianceCheck.id),
        )
        .group_by(ComplianceCheck.platform)
        .all()
    )
    platform_dict = {p: c for p, c in platforms}
    assert "1mg" in platform_dict
    assert "pharmeasy" in platform_dict
    session.close()
