"""Tests for DPCO compliance rules engine — deterministic checks."""

import pytest

from src.agents.compliance.dpco_rules import (
    WPI_FACTOR,
    ComplianceResult,
    Severity,
    Verdict,
    calculate_overcharge_with_interest,
    check_non_scheduled_drug,
    check_scheduled_drug,
    classify_severity,
)
from src.agents.compliance.rules_engine import DPCORulesEngine


# --- Severity Classification ---


def test_classify_severity_critical():
    assert classify_severity(60.0) == Severity.CRITICAL


def test_classify_severity_high():
    assert classify_severity(30.0) == Severity.HIGH


def test_classify_severity_medium():
    assert classify_severity(10.0) == Severity.MEDIUM


def test_classify_severity_low():
    assert classify_severity(3.0) == Severity.LOW


def test_classify_severity_boundary_50():
    assert classify_severity(50.1) == Severity.CRITICAL


def test_classify_severity_boundary_20():
    assert classify_severity(20.1) == Severity.HIGH


# --- Scheduled Drug Checks (Para 4-7) ---


def test_scheduled_compliant():
    """Price below ceiling = COMPLIANT."""
    result = check_scheduled_drug(retail_price=20.0, ceiling_price=25.0)
    assert result.verdict == Verdict.COMPLIANT
    assert result.overcharge_amount == 0.0
    assert result.confidence == 1.0


def test_scheduled_compliant_at_ceiling():
    """Price exactly at WPI-adjusted ceiling = COMPLIANT."""
    adjusted = 25.0 * WPI_FACTOR
    result = check_scheduled_drug(retail_price=adjusted, ceiling_price=25.0)
    assert result.verdict == Verdict.COMPLIANT


def test_scheduled_compliant_within_tolerance():
    """Price within 2% tolerance above ceiling = COMPLIANT."""
    adjusted = 25.0 * WPI_FACTOR
    within_tolerance = adjusted * 1.01  # 1% above (within 2% tolerance)
    result = check_scheduled_drug(retail_price=within_tolerance, ceiling_price=25.0)
    assert result.verdict == Verdict.COMPLIANT


def test_scheduled_warning():
    """Price slightly above ceiling (within 5%) = WARNING."""
    adjusted = 25.0 * WPI_FACTOR
    slightly_above = adjusted * 1.04  # 4% above (within warning zone)
    result = check_scheduled_drug(retail_price=slightly_above, ceiling_price=25.0)
    assert result.verdict == Verdict.WARNING
    assert result.severity == Severity.LOW


def test_scheduled_violation():
    """Price significantly above ceiling = VIOLATION."""
    result = check_scheduled_drug(retail_price=40.0, ceiling_price=25.0)
    assert result.verdict == Verdict.VIOLATION
    assert result.overcharge_amount > 0
    assert result.overcharge_pct > 0
    assert result.severity is not None


def test_scheduled_violation_critical():
    """Price > 50% above ceiling = CRITICAL violation."""
    adjusted = 25.0 * WPI_FACTOR
    critical_price = adjusted * 2.0  # 100% above
    result = check_scheduled_drug(retail_price=critical_price, ceiling_price=25.0)
    assert result.verdict == Verdict.VIOLATION
    assert result.severity == Severity.CRITICAL


def test_scheduled_dpco_sections_cited():
    """Violations should cite specific DPCO paragraphs."""
    result = check_scheduled_drug(retail_price=50.0, ceiling_price=25.0)
    assert "Para" in result.dpco_rule
    assert "15" in result.dpco_rule  # Para 15 for overcharging penalty


def test_scheduled_checked_by_rule_engine():
    """All deterministic checks marked as rule_engine."""
    result = check_scheduled_drug(retail_price=20.0, ceiling_price=25.0)
    assert result.checked_by == "rule_engine"


# --- Non-Scheduled Drug Checks (Para 20) ---


def test_non_scheduled_compliant():
    """Price increase within 10% = COMPLIANT."""
    result = check_non_scheduled_drug(current_price=108.0, previous_price=100.0)
    assert result.verdict == Verdict.COMPLIANT


def test_non_scheduled_compliant_exactly_10pct():
    """Price increase of exactly 10% = COMPLIANT."""
    result = check_non_scheduled_drug(current_price=110.0, previous_price=100.0)
    assert result.verdict == Verdict.COMPLIANT


def test_non_scheduled_violation():
    """Price increase > 10% = VIOLATION."""
    result = check_non_scheduled_drug(current_price=115.0, previous_price=100.0)
    assert result.verdict == Verdict.VIOLATION
    assert result.overcharge_amount > 0


def test_non_scheduled_no_previous():
    """No previous price = REVIEW_NEEDED."""
    result = check_non_scheduled_drug(current_price=115.0, previous_price=0.0)
    assert result.verdict == Verdict.REVIEW_NEEDED


# --- Overcharge Interest Calculation (Para 15) ---


def test_overcharge_with_interest():
    """Para 15: 15% p.a. interest on overcharged amount."""
    result = calculate_overcharge_with_interest(
        overcharge_per_unit=15.0,
        estimated_monthly_volume=1000,
        months=6,
    )
    assert result["total_overcharge"] == 90000.0  # 15 * 1000 * 6
    assert result["interest_amount"] == 6750.0  # 90000 * 0.15 * (6/12)
    assert result["total_recoverable"] == 96750.0


def test_overcharge_interest_one_year():
    result = calculate_overcharge_with_interest(
        overcharge_per_unit=10.0,
        estimated_monthly_volume=500,
        months=12,
    )
    assert result["total_overcharge"] == 60000.0
    assert result["interest_amount"] == 9000.0  # 60000 * 0.15 * 1
    assert result["total_recoverable"] == 69000.0


def test_overcharge_references_dpco():
    result = calculate_overcharge_with_interest(10, 100, 1)
    assert "Para 15" in result["dpco_reference"]


# --- Rules Engine Wrapper ---


def test_rules_engine_scheduled():
    engine = DPCORulesEngine()
    result = engine.check(
        retail_price=40.0,
        ceiling_price=25.0,
        is_scheduled=True,
    )
    assert result.verdict in [Verdict.VIOLATION, Verdict.WARNING]


def test_rules_engine_non_scheduled():
    engine = DPCORulesEngine()
    result = engine.check(
        retail_price=115.0,
        ceiling_price=None,
        is_scheduled=False,
        previous_price=100.0,
    )
    assert result.verdict == Verdict.VIOLATION


def test_rules_engine_scheduled_no_ceiling():
    engine = DPCORulesEngine()
    result = engine.check(
        retail_price=40.0,
        ceiling_price=None,
        is_scheduled=True,
    )
    assert result.verdict == Verdict.REVIEW_NEEDED


def test_rules_engine_non_scheduled_no_previous():
    engine = DPCORulesEngine()
    result = engine.check(
        retail_price=40.0,
        ceiling_price=None,
        is_scheduled=False,
        previous_price=None,
    )
    assert result.verdict == Verdict.REVIEW_NEEDED


def test_rules_engine_batch():
    engine = DPCORulesEngine()
    records = [
        {"retail_price": 20.0, "ceiling_price": 25.0, "is_scheduled": True},
        {"retail_price": 50.0, "ceiling_price": 25.0, "is_scheduled": True},
        {"retail_price": 108.0, "is_scheduled": False, "previous_price": 100.0},
    ]
    results = engine.check_batch(records)
    assert len(results) == 3
    assert results[0][1].verdict == Verdict.COMPLIANT
    assert results[1][1].verdict == Verdict.VIOLATION
    assert results[2][1].verdict == Verdict.COMPLIANT
