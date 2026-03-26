"""DPCO 2013 rule definitions — deterministic compliance checking."""

from dataclasses import dataclass
from enum import Enum


class Verdict(str, Enum):
    COMPLIANT = "compliant"
    VIOLATION = "violation"
    WARNING = "warning"
    REVIEW_NEEDED = "review_needed"


class Severity(str, Enum):
    CRITICAL = "critical"  # Overcharge > 50%
    HIGH = "high"  # Overcharge 20-50%
    MEDIUM = "medium"  # Overcharge 5-20%
    LOW = "low"  # Overcharge < 5%


# Current WPI factor (FY 2025-26)
WPI_FACTOR = 1.0174028
WPI_YEAR = "FY2025-26"

# DPCO 2013 parameters
NON_SCHEDULED_MAX_INCREASE = 0.10  # 10% per annum (Para 20)
OVERCHARGE_INTEREST_RATE = 0.15  # 15% p.a. (Para 15)
TOLERANCE_PCT = 0.02  # 2% tolerance for rounding/GST


@dataclass
class ComplianceResult:
    """Result of a DPCO compliance check."""

    verdict: Verdict
    severity: Severity | None
    overcharge_amount: float  # Per unit (retail - ceiling)
    overcharge_pct: float  # Percentage overcharge
    dpco_rule: str  # Which DPCO paragraph applied
    reasoning: str  # Brief explanation
    confidence: float  # 0-1 (1.0 for deterministic rules)
    checked_by: str  # "rule_engine" or "llm_8b" or "llm_70b"


def classify_severity(overcharge_pct: float) -> Severity:
    """Classify violation severity based on overcharge percentage."""
    if overcharge_pct > 50:
        return Severity.CRITICAL
    elif overcharge_pct > 20:
        return Severity.HIGH
    elif overcharge_pct > 5:
        return Severity.MEDIUM
    else:
        return Severity.LOW


def check_scheduled_drug(
    retail_price: float,
    ceiling_price: float,
) -> ComplianceResult:
    """
    Para 4-7: Check if scheduled drug price exceeds ceiling price.

    Ceiling price is adjusted by current WPI factor.
    A 2% tolerance is allowed for rounding and GST variations.
    """
    adjusted_ceiling = ceiling_price * WPI_FACTOR
    tolerance_ceiling = adjusted_ceiling * (1 + TOLERANCE_PCT)

    if retail_price <= tolerance_ceiling:
        return ComplianceResult(
            verdict=Verdict.COMPLIANT,
            severity=None,
            overcharge_amount=0.0,
            overcharge_pct=0.0,
            dpco_rule="Para 4-7 (Scheduled Formulation)",
            reasoning=(
                f"Retail Rs {retail_price:.2f} is within "
                f"WPI-adjusted ceiling Rs {adjusted_ceiling:.2f} "
                f"(+2% tolerance = Rs {tolerance_ceiling:.2f})"
            ),
            confidence=1.0,
            checked_by="rule_engine",
        )

    overcharge = retail_price - adjusted_ceiling
    overcharge_pct = (overcharge / adjusted_ceiling) * 100

    # Warning zone: within 5% above ceiling
    if overcharge_pct <= 5:
        verdict = Verdict.WARNING
    else:
        verdict = Verdict.VIOLATION

    return ComplianceResult(
        verdict=verdict,
        severity=classify_severity(overcharge_pct),
        overcharge_amount=round(overcharge, 2),
        overcharge_pct=round(overcharge_pct, 2),
        dpco_rule="Para 4-7, 15, 16 (Scheduled Formulation)",
        reasoning=(
            f"Retail Rs {retail_price:.2f} exceeds "
            f"WPI-adjusted ceiling Rs {adjusted_ceiling:.2f} "
            f"by Rs {overcharge:.2f} ({overcharge_pct:.1f}%). "
            f"Under Para 15, manufacturer liable for overcharged amount "
            f"+ 15% p.a. interest."
        ),
        confidence=1.0,
        checked_by="rule_engine",
    )


def check_non_scheduled_drug(
    current_price: float,
    previous_price: float,
) -> ComplianceResult:
    """
    Para 20: Non-scheduled drugs cannot increase MRP by more than 10% in 12 months.
    """
    if previous_price <= 0:
        return ComplianceResult(
            verdict=Verdict.REVIEW_NEEDED,
            severity=None,
            overcharge_amount=0.0,
            overcharge_pct=0.0,
            dpco_rule="Para 20 (Non-scheduled)",
            reasoning="No previous price available for 10% increase check",
            confidence=0.5,
            checked_by="rule_engine",
        )

    max_allowed = previous_price * (1 + NON_SCHEDULED_MAX_INCREASE)

    if current_price <= max_allowed:
        return ComplianceResult(
            verdict=Verdict.COMPLIANT,
            severity=None,
            overcharge_amount=0.0,
            overcharge_pct=0.0,
            dpco_rule="Para 20 (Non-scheduled, 10% cap)",
            reasoning=(
                f"Current Rs {current_price:.2f} within 10% increase "
                f"from Rs {previous_price:.2f} "
                f"(max allowed: Rs {max_allowed:.2f})"
            ),
            confidence=1.0,
            checked_by="rule_engine",
        )

    overcharge = current_price - max_allowed
    overcharge_pct = (overcharge / max_allowed) * 100

    return ComplianceResult(
        verdict=Verdict.VIOLATION,
        severity=classify_severity(overcharge_pct),
        overcharge_amount=round(overcharge, 2),
        overcharge_pct=round(overcharge_pct, 2),
        dpco_rule="Para 20 (Non-scheduled, 10% cap)",
        reasoning=(
            f"Current Rs {current_price:.2f} exceeds 10% annual increase "
            f"from Rs {previous_price:.2f} "
            f"(max allowed: Rs {max_allowed:.2f}, excess: Rs {overcharge:.2f})"
        ),
        confidence=1.0,
        checked_by="rule_engine",
    )


def calculate_overcharge_with_interest(
    overcharge_per_unit: float,
    estimated_monthly_volume: int,
    months: int,
) -> dict:
    """
    Para 15: Calculate total overcharged amount + 15% p.a. interest.
    """
    total_overcharge = overcharge_per_unit * estimated_monthly_volume * months
    interest = total_overcharge * OVERCHARGE_INTEREST_RATE * (months / 12)

    return {
        "overcharge_per_unit": round(overcharge_per_unit, 2),
        "estimated_monthly_volume": estimated_monthly_volume,
        "months": months,
        "total_overcharge": round(total_overcharge, 2),
        "interest_rate": f"{OVERCHARGE_INTEREST_RATE * 100}% p.a.",
        "interest_amount": round(interest, 2),
        "total_recoverable": round(total_overcharge + interest, 2),
        "dpco_reference": "Para 15, DPCO 2013",
    }
