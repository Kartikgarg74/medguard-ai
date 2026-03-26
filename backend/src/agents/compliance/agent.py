"""Compliance Checker Agent — orchestrates rules engine + LLM edge cases."""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from src.agents.base import BaseAgent
from src.agents.compliance.dpco_rules import ComplianceResult, Verdict
from src.agents.compliance.edge_case_llm import EdgeCaseLLM
from src.agents.compliance.rules_engine import DPCORulesEngine
from src.ai.router import AIRouter
from src.database.models import CeilingPrice, ComplianceCheck, Medicine, RetailPrice
from src.database.session import get_session
from src.security.audit_log import log_audit
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _compute_audit_hash(input_data: dict, result: ComplianceResult) -> str:
    """Compute SHA-256 hash of input+output for tamper detection."""
    combined = json.dumps(
        {"input": input_data, "output": result.__dict__},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(combined.encode()).hexdigest()


class ComplianceAgent(BaseAgent):
    """
    Checks retail prices against DPCO ceiling prices.

    Strategy:
    1. Rules engine handles clear cases (deterministic, zero-cost)
    2. LLM handles edge cases (ambiguous matches, combination drugs)
    3. LLM CANNOT override a rule-engine VIOLATION (guardrail)
    """

    def __init__(self, ai_config: dict | None = None):
        super().__init__(name="compliance")
        self.rules_engine = DPCORulesEngine()
        self.router = AIRouter(ai_config or {})
        self.edge_case_llm = EdgeCaseLLM(self.router)

    async def execute(self, **kwargs) -> dict:
        """
        Run compliance checks on all unprocessed retail prices.

        Returns summary: {total_checked, violations, compliant, warnings, review_needed}
        """
        session = get_session()
        stats = {
            "total_checked": 0,
            "compliant": 0,
            "violations": 0,
            "warnings": 0,
            "review_needed": 0,
            "llm_calls": 0,
        }

        try:
            # Get retail prices that haven't been checked yet
            checked_ids = (
                session.query(ComplianceCheck.retail_price_id)
                .filter(ComplianceCheck.retail_price_id.isnot(None))
                .all()
            )
            checked_id_set = {row[0] for row in checked_ids}

            retail_prices = session.query(RetailPrice).all()
            unchecked = [rp for rp in retail_prices if rp.id not in checked_id_set]

            logger.info(f"Found {len(unchecked)} unchecked retail prices")

            for rp in unchecked:
                medicine = session.query(Medicine).filter_by(id=rp.medicine_id).first()
                if not medicine:
                    continue

                # Find ceiling price for this medicine
                ceiling = (
                    session.query(CeilingPrice)
                    .filter_by(medicine_id=medicine.id)
                    .order_by(CeilingPrice.scraped_at.desc())
                    .first()
                )

                ceiling_val = ceiling.ceiling_price if ceiling else None

                # Step 1: Run deterministic rules engine
                result = self.rules_engine.check(
                    retail_price=rp.selling_price,
                    ceiling_price=ceiling_val,
                    is_scheduled=medicine.dpco_scheduled or False,
                )

                # Step 2: If REVIEW_NEEDED and we have an AI router, try LLM
                if result.verdict == Verdict.REVIEW_NEEDED and self.router.groq:
                    try:
                        result = self.edge_case_llm.analyze_compliance(
                            medicine_name=medicine.name,
                            salt_composition=medicine.salt_composition or "",
                            formulation=medicine.formulation or "",
                            pack_size=rp.pack_size or "",
                            retail_price=rp.listed_price,
                            selling_price=rp.selling_price,
                            ceiling_price=ceiling_val or 0,
                            platform=rp.platform,
                        )
                        stats["llm_calls"] += 1
                    except Exception as e:
                        logger.warning(f"LLM edge case failed: {e}")
                        # Keep the REVIEW_NEEDED result from rules engine

                # GUARDRAIL: LLM cannot downgrade a rule-engine VIOLATION
                # (This check is implicit since we only call LLM for REVIEW_NEEDED)

                # Compute audit hash
                input_data = {
                    "medicine_id": medicine.id,
                    "retail_price": rp.selling_price,
                    "ceiling_price": ceiling_val,
                    "platform": rp.platform,
                }
                audit_hash = _compute_audit_hash(input_data, result)

                # Save compliance check
                cc = ComplianceCheck(
                    id=str(uuid.uuid4()),
                    medicine_id=medicine.id,
                    retail_price_id=rp.id,
                    ceiling_price_id=ceiling.id if ceiling else None,
                    platform=rp.platform,
                    ceiling_price=ceiling_val,
                    retail_price=rp.selling_price,
                    overcharge_amount=result.overcharge_amount,
                    overcharge_pct=result.overcharge_pct,
                    status=result.verdict.value,
                    severity=result.severity.value if result.severity else None,
                    dpco_rule_applied=result.dpco_rule,
                    llm_reasoning=result.reasoning,
                    confidence_score=result.confidence,
                    checked_by=result.checked_by,
                    audit_hash=audit_hash,
                    checked_at=datetime.now(timezone.utc),
                )
                session.add(cc)

                # Update stats
                stats["total_checked"] += 1
                if result.verdict == Verdict.COMPLIANT:
                    stats["compliant"] += 1
                elif result.verdict == Verdict.VIOLATION:
                    stats["violations"] += 1
                elif result.verdict == Verdict.WARNING:
                    stats["warnings"] += 1
                else:
                    stats["review_needed"] += 1

            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Compliance check failed: {e}")
            raise
        finally:
            session.close()

        log_audit(
            agent_name="compliance",
            action="compliance.batch_complete",
            output_data=stats,
        )

        logger.info(
            f"Compliance check complete: {stats['total_checked']} checked, "
            f"{stats['violations']} violations, {stats['compliant']} compliant"
        )

        return stats
