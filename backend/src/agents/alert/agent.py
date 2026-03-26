"""Alert Agent — routes violation alerts by severity to appropriate channels."""

import uuid
from datetime import datetime, timezone

from src.agents.base import BaseAgent
from src.database.models import Alert, ComplianceCheck, Medicine
from src.database.session import get_session
from src.security.audit_log import log_audit
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Severity -> channel routing
ALERT_ROUTING = {
    "critical": ["telegram_immediate"],
    "high": ["telegram_immediate"],
    "medium": ["telegram_batch"],
    "low": ["log_only"],
}

# Deduplication window (seconds) — don't re-alert same violation within this period
DEDUP_WINDOW_SECONDS = 86400  # 24 hours


class AlertAgent(BaseAgent):
    """Dispatches violation alerts based on severity routing rules."""

    def __init__(self, telegram_bot=None):
        super().__init__(name="alert")
        self.telegram_bot = telegram_bot
        self._recent_alerts: dict[str, datetime] = {}

    def _is_duplicate(self, check_id: str) -> bool:
        """Check if this violation was already alerted within the dedup window."""
        if check_id in self._recent_alerts:
            elapsed = (datetime.now(timezone.utc) - self._recent_alerts[check_id]).total_seconds()
            if elapsed < DEDUP_WINDOW_SECONDS:
                return True
        return False

    def _mark_alerted(self, check_id: str):
        self._recent_alerts[check_id] = datetime.now(timezone.utc)

        # Clean old entries
        now = datetime.now(timezone.utc)
        expired = [
            k
            for k, v in self._recent_alerts.items()
            if (now - v).total_seconds() > DEDUP_WINDOW_SECONDS
        ]
        for k in expired:
            del self._recent_alerts[k]

    async def execute(self, severity_threshold: str = "high", **kwargs) -> dict:
        """
        Process new violations and dispatch alerts.

        Args:
            severity_threshold: Minimum severity to alert on (critical/high/medium/low)
        """
        threshold_order = ["critical", "high", "medium", "low"]
        threshold_idx = threshold_order.index(severity_threshold)
        eligible_severities = threshold_order[: threshold_idx + 1]

        session = get_session()
        stats = {"processed": 0, "alerted": 0, "deduplicated": 0, "channels": {}}

        try:
            # Find violations not yet alerted
            alerted_ids = {row[0] for row in session.query(Alert.compliance_check_id).all()}

            violations = (
                session.query(ComplianceCheck, Medicine.name)
                .join(Medicine, ComplianceCheck.medicine_id == Medicine.id)
                .filter(
                    ComplianceCheck.status == "violation",
                    ComplianceCheck.severity.in_(eligible_severities),
                )
                .all()
            )

            for check, medicine_name in violations:
                stats["processed"] += 1

                if check.id in alerted_ids:
                    continue

                if self._is_duplicate(check.id):
                    stats["deduplicated"] += 1
                    continue

                # Determine channels
                channels = ALERT_ROUTING.get(check.severity or "low", ["log_only"])

                for channel in channels:
                    message = self._format_alert(check, medicine_name)

                    # Send via Telegram if available
                    if "telegram" in channel and self.telegram_bot:
                        try:
                            await self.telegram_bot.send_violation_alert(
                                medicine_name=medicine_name,
                                platform=check.platform,
                                overcharge_pct=check.overcharge_pct or 0,
                                overcharge_amount=check.overcharge_amount or 0,
                                severity=check.severity or "low",
                                dpco_rule=check.dpco_rule_applied or "",
                            )
                        except Exception as e:
                            logger.warning(f"Telegram alert failed: {e}")

                    # Save alert record
                    alert = Alert(
                        id=str(uuid.uuid4()),
                        compliance_check_id=check.id,
                        channel=channel,
                        severity=check.severity or "low",
                        message=message,
                        status="sent",
                        sent_at=datetime.now(timezone.utc),
                    )
                    session.add(alert)

                    stats["alerted"] += 1
                    stats["channels"][channel] = stats["channels"].get(channel, 0) + 1

                self._mark_alerted(check.id)

            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Alert dispatch failed: {e}")
            raise
        finally:
            session.close()

        log_audit(
            agent_name="alert",
            action="alert.dispatch",
            output_data=stats,
        )

        logger.info(
            f"Alerts dispatched: {stats['alerted']} sent, {stats['deduplicated']} deduplicated"
        )
        return stats

    def _format_alert(self, check: ComplianceCheck, medicine_name: str) -> str:
        """Format a violation into an alert message."""
        severity_icons = {
            "critical": "!!",
            "high": "!",
            "medium": "*",
            "low": "-",
        }
        icon = severity_icons.get(check.severity or "low", "-")
        return (
            f"[{icon} {(check.severity or 'low').upper()}] "
            f"{medicine_name} on {check.platform}\n"
            f"MRP: Rs {check.retail_price:.2f} | "
            f"Ceiling: Rs {check.ceiling_price:.2f}\n"
            f"Overcharge: Rs {check.overcharge_amount:.2f} "
            f"({check.overcharge_pct:.1f}%)\n"
            f"DPCO: {check.dpco_rule_applied}"
        )
