"""Reporter Agent — generates compliance reports with LLM narratives."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func

from src.agents.base import BaseAgent
from src.agents.reporter.generator import (
    render_daily_summary,
    render_violation_report,
    save_report_html,
)
from src.ai.prompts import REPORT_NARRATIVE_PROMPT, REPORT_NARRATIVE_SYSTEM
from src.ai.router import AIRouter
from src.database.models import ComplianceCheck, Medicine, Report
from src.database.session import get_session
from src.security.audit_log import log_audit
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReporterAgent(BaseAgent):
    """Generates compliance reports with LLM-powered narrative analysis."""

    def __init__(self, ai_config: dict | None = None):
        super().__init__(name="reporter")
        self.router = AIRouter(ai_config or {})

    async def execute(self, report_type: str = "daily_summary", **kwargs) -> dict:
        """Generate a compliance report."""
        session = get_session()

        try:
            # Gather data
            stats = self._get_compliance_stats(session)
            violations = self._get_violations(session)
            platform_stats = self._get_platform_stats(session)
            top_violations = self._get_top_violations(session, limit=10)

            # Generate LLM narrative (if router available)
            narrative = ""
            if self.router.groq and violations:
                narrative = self._generate_narrative(stats, top_violations, platform_stats)

            # Render report
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            if report_type == "violation_detail":
                html = render_violation_report(
                    period=today,
                    total_checked=stats["total_checked"],
                    total_violations=stats["violations"],
                    compliance_rate=stats["compliance_rate"],
                    violations=violations,
                    platform_stats=platform_stats,
                    narrative=narrative,
                )
                filename = f"violation_report_{today}.html"
            else:
                html = render_daily_summary(
                    date_str=today,
                    stats=stats,
                    top_violations=top_violations,
                    platform_breakdown=platform_stats,
                )
                filename = f"daily_summary_{today}.html"

            # Save to disk
            file_path = save_report_html(html, filename)

            # Save report record to DB
            report = Report(
                id=str(uuid.uuid4()),
                report_type=report_type,
                title=f"MedGuard Report — {today}",
                generated_by="reporter_agent",
                content_html=html,
                file_path=file_path,
                total_medicines_checked=stats["total_checked"],
                total_violations=stats["violations"],
                compliance_rate=stats["compliance_rate"],
                generated_at=datetime.now(timezone.utc),
            )
            session.add(report)
            session.commit()

            log_audit(
                agent_name="reporter",
                action="report.generate",
                resource_type="report",
                resource_id=report.id,
                output_data={
                    "type": report_type,
                    "violations": stats["violations"],
                    "file": file_path,
                },
            )

            return {
                "report_id": report.id,
                "type": report_type,
                "file_path": file_path,
                "stats": stats,
            }

        finally:
            session.close()

    def _get_compliance_stats(self, session) -> dict:
        total = session.query(func.count(ComplianceCheck.id)).scalar() or 0
        violations = (
            session.query(func.count(ComplianceCheck.id))
            .filter(ComplianceCheck.status == "violation")
            .scalar()
            or 0
        )
        warnings = (
            session.query(func.count(ComplianceCheck.id))
            .filter(ComplianceCheck.status == "warning")
            .scalar()
            or 0
        )
        rate = round(((total - violations) / total * 100), 1) if total > 0 else 100.0

        return {
            "total_checked": total,
            "violations": violations,
            "warnings": warnings,
            "compliant": total - violations - warnings,
            "compliance_rate": rate,
        }

    def _get_violations(self, session) -> list[dict]:
        checks = (
            session.query(ComplianceCheck, Medicine.name)
            .join(Medicine, ComplianceCheck.medicine_id == Medicine.id)
            .filter(ComplianceCheck.status.in_(["violation", "warning"]))
            .order_by(ComplianceCheck.overcharge_pct.desc())
            .limit(50)
            .all()
        )

        return [
            {
                "medicine_name": name,
                "platform": cc.platform,
                "retail_price": cc.retail_price or 0,
                "ceiling_price": cc.ceiling_price or 0,
                "overcharge_amount": cc.overcharge_amount or 0,
                "overcharge_pct": cc.overcharge_pct or 0,
                "severity": cc.severity or "low",
                "dpco_rule": cc.dpco_rule_applied or "",
            }
            for cc, name in checks
        ]

    def _get_platform_stats(self, session) -> dict:
        platforms = (
            session.query(
                ComplianceCheck.platform,
                func.count(ComplianceCheck.id),
                func.sum(
                    func.case(
                        (ComplianceCheck.status == "violation", 1),
                        else_=0,
                    )
                ),
            )
            .group_by(ComplianceCheck.platform)
            .all()
        )

        result = {}
        for platform, total, violations in platforms:
            violations = violations or 0
            rate = round(((total - violations) / total * 100), 1) if total > 0 else 100.0
            avg_overcharge_q = (
                session.query(func.avg(ComplianceCheck.overcharge_amount))
                .filter(
                    ComplianceCheck.platform == platform,
                    ComplianceCheck.status == "violation",
                )
                .scalar()
            )
            result[platform] = {
                "checked": total,
                "violations": violations,
                "compliance_rate": rate,
                "avg_overcharge": round(avg_overcharge_q or 0, 2),
            }

        return result

    def _get_top_violations(self, session, limit: int = 10) -> list[dict]:
        checks = (
            session.query(ComplianceCheck, Medicine.name)
            .join(Medicine, ComplianceCheck.medicine_id == Medicine.id)
            .filter(ComplianceCheck.status == "violation")
            .order_by(ComplianceCheck.overcharge_pct.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "medicine_name": name,
                "platform": cc.platform,
                "overcharge_amount": cc.overcharge_amount or 0,
                "overcharge_pct": cc.overcharge_pct or 0,
                "severity": cc.severity or "low",
            }
            for cc, name in checks
        ]

    def _generate_narrative(
        self, stats: dict, top_violations: list[dict], platform_stats: dict
    ) -> str:
        """Generate LLM narrative for the report."""
        platform_text = "\n".join(
            f"- {p}: {s['checked']} checked, {s['violations']} violations, "
            f"{s['compliance_rate']}% compliant"
            for p, s in platform_stats.items()
        )

        top_v_text = "\n".join(
            f"- {v['medicine_name']} on {v['platform']}: "
            f"Rs {v['overcharge_amount']:.2f} overcharge "
            f"({v['overcharge_pct']:.1f}%, {v['severity']})"
            for v in top_violations[:5]
        )

        prompt = REPORT_NARRATIVE_PROMPT.format(
            period=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            total_checked=stats["total_checked"],
            total_violations=stats["violations"],
            compliance_rate=stats["compliance_rate"],
            platform_breakdown=platform_text or "No platform data available",
            top_violations=top_v_text or "No violations found",
        )

        try:
            result = self.router.route(
                task="report_narrative",
                prompt=prompt,
                system_prompt=REPORT_NARRATIVE_SYSTEM,
            )
            return result
        except Exception as e:
            logger.warning(f"LLM narrative generation failed: {e}")
            return ""
