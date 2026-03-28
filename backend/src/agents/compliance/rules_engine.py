"""Deterministic DPCO compliance rules engine."""

import logging

from src.agents.compliance.dpco_rules import (
    ComplianceResult,
    Verdict,
    check_non_scheduled_drug,
    check_scheduled_drug,
)

logger = logging.getLogger(__name__)


class DPCORulesEngine:
    """Deterministic DPCO 2013 rules engine — no LLM, pure logic."""

    def check(
        self,
        retail_price: float,
        ceiling_price: float | None,
        is_scheduled: bool,
        previous_price: float | None = None,
    ) -> ComplianceResult:
        """
        Run DPCO compliance check.

        For scheduled drugs: compare retail vs ceiling price.
        For non-scheduled drugs: check 10% annual increase cap.
        """
        if is_scheduled and ceiling_price is not None and ceiling_price > 0:
            return check_scheduled_drug(retail_price, ceiling_price)

        if not is_scheduled and previous_price is not None:
            return check_non_scheduled_drug(retail_price, previous_price)

        # No ceiling price available for scheduled drug — needs review
        if is_scheduled:
            return ComplianceResult(
                verdict=Verdict.REVIEW_NEEDED,
                severity=None,
                overcharge_amount=0.0,
                overcharge_pct=0.0,
                dpco_rule="Para 4-7 (Missing ceiling price)",
                reasoning=(
                    "Scheduled drug but no NPPA ceiling price found. "
                    "Requires manual lookup or LLM analysis."
                ),
                confidence=0.3,
                checked_by="rule_engine",
            )

        # Non-scheduled, no previous price
        return ComplianceResult(
            verdict=Verdict.REVIEW_NEEDED,
            severity=None,
            overcharge_amount=0.0,
            overcharge_pct=0.0,
            dpco_rule="Para 20 (Insufficient data)",
            reasoning=(
                "Non-scheduled drug with no previous price data. "
                "Cannot verify 10% annual increase cap."
            ),
            confidence=0.3,
            checked_by="rule_engine",
        )

    def check_batch(self, records: list[dict]) -> list[tuple[dict, ComplianceResult]]:
        """
        Check a batch of records.

        Each record dict must have:
          - retail_price: float
          - ceiling_price: float | None
          - is_scheduled: bool
          - previous_price: float | None (optional)
        """
        results = []
        for record in records:
            result = self.check(
                retail_price=record["retail_price"],
                ceiling_price=record.get("ceiling_price"),
                is_scheduled=record.get("is_scheduled", False),
                previous_price=record.get("previous_price"),
            )
            results.append((record, result))
        return results
