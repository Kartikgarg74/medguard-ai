"""LLM-powered edge case handler for ambiguous compliance scenarios."""

import logging

from src.agents.compliance.dpco_rules import (
    ComplianceResult,
    Verdict,
    classify_severity,
)
from src.ai.prompts import (
    COMPLIANCE_CHECK_PROMPT,
    COMPLIANCE_CHECK_SYSTEM,
    EDGE_CASE_PROMPT,
    EDGE_CASE_SYSTEM,
)
from src.ai.router import AIRouter

logger = logging.getLogger(__name__)


class EdgeCaseLLM:
    """Handles ambiguous compliance cases using LLM (Groq)."""

    def __init__(self, router: AIRouter):
        self.router = router

    def analyze_compliance(
        self,
        medicine_name: str,
        salt_composition: str,
        formulation: str,
        pack_size: str,
        retail_price: float,
        selling_price: float,
        ceiling_price: float,
        platform: str,
    ) -> ComplianceResult:
        """Use LLM to analyze an ambiguous compliance case."""
        prompt = COMPLIANCE_CHECK_PROMPT.format(
            medicine_name=medicine_name,
            salt_composition=salt_composition,
            formulation=formulation,
            pack_size=pack_size,
            retail_price=retail_price,
            selling_price=selling_price,
            ceiling_price=ceiling_price,
            platform=platform,
        )

        try:
            result = self.router.route_json(
                task="compliance_check",
                prompt=prompt,
                system_prompt=COMPLIANCE_CHECK_SYSTEM,
            )
            return self._parse_llm_result(result)
        except Exception as e:
            logger.error(f"LLM compliance check failed: {e}")
            return ComplianceResult(
                verdict=Verdict.REVIEW_NEEDED,
                severity=None,
                overcharge_amount=0.0,
                overcharge_pct=0.0,
                dpco_rule="LLM analysis failed",
                reasoning=f"LLM error: {str(e)[:100]}",
                confidence=0.0,
                checked_by="llm_error",
            )

    def analyze_medicine_match(
        self,
        product_name: str,
        platform: str,
        retail_price: float,
        pack_size: str,
        catalog_name: str,
        catalog_salt: str,
        match_score: float,
    ) -> dict:
        """Use LLM to determine if a scraped product matches a catalog entry."""
        prompt = EDGE_CASE_PROMPT.format(
            product_name=product_name,
            platform=platform,
            retail_price=retail_price,
            pack_size=pack_size,
            catalog_name=catalog_name,
            catalog_salt=catalog_salt,
            match_score=match_score,
        )

        try:
            return self.router.route_json(
                task="edge_case",
                prompt=prompt,
                system_prompt=EDGE_CASE_SYSTEM,
            )
        except Exception as e:
            logger.error(f"LLM medicine match failed: {e}")
            return {
                "same_medicine": None,
                "confidence": 0.0,
                "reasoning": f"LLM error: {str(e)[:100]}",
                "needs_human_review": True,
            }

    def _parse_llm_result(self, result: dict) -> ComplianceResult:
        """Parse LLM JSON response into a ComplianceResult."""
        verdict_str = result.get("verdict", "review_needed").lower()
        verdict_map = {
            "compliant": Verdict.COMPLIANT,
            "violation": Verdict.VIOLATION,
            "warning": Verdict.WARNING,
            "review_needed": Verdict.REVIEW_NEEDED,
        }
        verdict = verdict_map.get(verdict_str, Verdict.REVIEW_NEEDED)

        overcharge = float(result.get("overcharge_per_unit", 0))
        confidence = float(result.get("confidence", 0.5))

        # Calculate overcharge percentage if we have the data
        suggested_max = float(result.get("suggested_max_price", 0))
        if suggested_max > 0 and overcharge > 0:
            overcharge_pct = (overcharge / suggested_max) * 100
        else:
            overcharge_pct = 0.0

        severity = classify_severity(overcharge_pct) if verdict == Verdict.VIOLATION else None

        sections = result.get("dpco_sections", [])
        dpco_rule = ", ".join(sections) if sections else "LLM analysis"

        return ComplianceResult(
            verdict=verdict,
            severity=severity,
            overcharge_amount=round(overcharge, 2),
            overcharge_pct=round(overcharge_pct, 2),
            dpco_rule=dpco_rule,
            reasoning=result.get("reasoning", "")[:500],
            confidence=confidence,
            checked_by="llm_8b",
        )
