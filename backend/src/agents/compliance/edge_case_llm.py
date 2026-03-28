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
from src.security.prompt_guard import sanitize_input

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
            medicine_name=sanitize_input(medicine_name, max_length=200),
            salt_composition=sanitize_input(salt_composition, max_length=500),
            formulation=sanitize_input(formulation, max_length=100),
            pack_size=sanitize_input(pack_size, max_length=100),
            retail_price=retail_price,
            selling_price=selling_price,
            ceiling_price=ceiling_price,
            platform=sanitize_input(platform, max_length=50),
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
            product_name=sanitize_input(product_name, max_length=200),
            platform=sanitize_input(platform, max_length=50),
            retail_price=retail_price,
            pack_size=sanitize_input(pack_size, max_length=100),
            catalog_name=sanitize_input(catalog_name, max_length=200),
            catalog_salt=sanitize_input(catalog_salt, max_length=500),
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
        verdict_str = str(result.get("verdict", "review_needed")).lower().strip()
        verdict_map = {
            "compliant": Verdict.COMPLIANT,
            "violation": Verdict.VIOLATION,
            "warning": Verdict.WARNING,
            "review_needed": Verdict.REVIEW_NEEDED,
        }
        if verdict_str not in verdict_map:
            logger.warning(f"LLM returned unexpected verdict: {verdict_str!r}")
        verdict = verdict_map.get(verdict_str, Verdict.REVIEW_NEEDED)

        # Clamp numeric values to sensible ranges
        overcharge = max(0.0, min(float(result.get("overcharge_per_unit", 0)), 100000.0))
        confidence = max(0.0, min(float(result.get("confidence", 0.5)), 1.0))

        # Calculate overcharge percentage if we have the data
        suggested_max = max(0.0, min(float(result.get("suggested_max_price", 0)), 100000.0))
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
            reasoning=sanitize_input(str(result.get("reasoning", "")), max_length=500),
            confidence=confidence,
            checked_by="llm_8b",
        )
