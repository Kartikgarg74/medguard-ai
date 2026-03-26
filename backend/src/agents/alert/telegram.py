"""Telegram bot for MedGuard AI violation alerts and commands."""

import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)

# HMAC secret for callback data signing
_HMAC_SECRET = os.getenv("MEDGUARD_ENCRYPTION_KEY", "medguard-default-key").encode()


def sign_callback_data(data: str) -> str:
    """Sign callback data with HMAC-SHA256 to prevent tampering."""
    sig = hmac.new(_HMAC_SECRET, data.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{data}|{sig}"


def verify_callback_data(signed_data: str) -> str | None:
    """Verify HMAC signature. Returns data if valid, None if tampered."""
    if "|" not in signed_data:
        return None
    data, sig = signed_data.rsplit("|", 1)
    expected = hmac.new(_HMAC_SECRET, data.encode(), hashlib.sha256).hexdigest()[:16]
    if hmac.compare_digest(sig, expected):
        return data
    return None


SEVERITY_COLORS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}


class MedGuardTelegramBot:
    """Telegram bot for MedGuard AI alerts."""

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self._bot = None

    async def _get_bot(self):
        """Lazy-load the telegram bot."""
        if self._bot is None:
            if not self.bot_token:
                raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
            from telegram import Bot

            self._bot = Bot(token=self.bot_token)
        return self._bot

    async def send_violation_alert(
        self,
        medicine_name: str,
        platform: str,
        overcharge_pct: float,
        overcharge_amount: float,
        severity: str,
        dpco_rule: str,
    ):
        """Send a formatted violation alert to Telegram."""
        icon = SEVERITY_COLORS.get(severity, "⚪")

        message = (
            f"{icon} <b>DPCO Violation Detected</b>\n\n"
            f"<b>Medicine:</b> {medicine_name}\n"
            f"<b>Platform:</b> {platform}\n"
            f"<b>Overcharge:</b> Rs {overcharge_amount:.2f} "
            f"({overcharge_pct:.1f}%)\n"
            f"<b>Severity:</b> {severity.upper()}\n"
            f"<b>DPCO Rule:</b> {dpco_rule}\n\n"
            f"<i>MedGuard AI — Automated Compliance Monitoring</i>"
        )

        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
            )
            logger.info(f"Telegram alert sent: {medicine_name} ({severity})")
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            raise

    async def send_daily_summary(
        self,
        total_checked: int,
        violations: int,
        compliance_rate: float,
        top_violations: list[dict],
    ):
        """Send daily compliance summary to Telegram."""
        top_text = ""
        for v in top_violations[:5]:
            icon = SEVERITY_COLORS.get(v.get("severity", "low"), "⚪")
            top_text += (
                f"  {icon} {v['medicine_name']} — "
                f"Rs {v['overcharge_amount']:.2f} "
                f"({v['overcharge_pct']:.1f}%)\n"
            )

        message = (
            f"📊 <b>MedGuard Daily Summary</b>\n\n"
            f"Medicines checked: <b>{total_checked}</b>\n"
            f"Violations found: <b>{violations}</b>\n"
            f"Compliance rate: <b>{compliance_rate:.1f}%</b>\n\n"
        )
        if top_text:
            message += f"<b>Top Violations:</b>\n{top_text}\n"

        message += "<i>MedGuard AI — DPCO 2013 Compliance</i>"

        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Telegram summary failed: {e}")

    async def send_pipeline_status(self, status: dict):
        """Send pipeline completion status."""
        message = (
            f"⚙️ <b>Pipeline Complete</b>\n\n"
            f"NPPA: {status.get('nppa', {}).get('found', 0)} ceiling prices\n"
            f"Pharmacies: {status.get('total_prices', 0)} retail prices\n"
            f"Violations: {status.get('violations', 0)}\n"
        )

        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Telegram status failed: {e}")
