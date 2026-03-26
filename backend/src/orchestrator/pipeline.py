"""Main pipeline — orchestrates scrape -> check -> report -> alert."""

import time
import uuid
from datetime import datetime, timezone
from enum import Enum

from src.agents.alert.agent import AlertAgent
from src.agents.alert.telegram import MedGuardTelegramBot
from src.agents.compliance.agent import ComplianceAgent
from src.agents.reporter.agent import ReporterAgent
from src.agents.scraper.agent import ScraperAgent
from src.orchestrator.message_bus import Message, get_message_bus
from src.security.audit_log import log_audit
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineStatus(str, Enum):
    IDLE = "idle"
    SCRAPING = "scraping"
    CHECKING = "checking"
    REPORTING = "reporting"
    ALERTING = "alerting"
    COMPLETED = "completed"
    FAILED = "failed"


class MedGuardPipeline:
    """
    Full pipeline: scrape -> compliance check -> report -> alert.

    Each stage publishes messages to the bus for observability.
    """

    def __init__(self, ai_config: dict | None = None):
        self.scraper = ScraperAgent()
        self.compliance = ComplianceAgent(ai_config)
        self.reporter = ReporterAgent(ai_config)

        # Telegram bot (optional)
        telegram_bot = MedGuardTelegramBot()
        self.alert = AlertAgent(telegram_bot=telegram_bot)

        self.bus = get_message_bus()
        self.status = PipelineStatus.IDLE
        self.last_run: datetime | None = None
        self.last_result: dict | None = None
        self._run_count = 0

    async def run_full_scan(
        self,
        medicine_names: list[str] | None = None,
        platforms: list[str] | None = None,
        max_concurrent: int = 3,
    ) -> dict:
        """
        Execute the full pipeline end-to-end.

        1. Scrape NPPA ceiling prices + pharmacy retail prices
        2. Run compliance checks on all new prices
        3. Generate compliance report
        4. Dispatch alerts for violations

        Returns pipeline result summary.
        """
        run_id = str(uuid.uuid4())
        self._run_count += 1
        start_time = time.time()
        result = {
            "run_id": run_id,
            "run_number": self._run_count,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "stages": {},
        }

        logger.info(f"Pipeline run #{self._run_count} starting (id={run_id[:8]})")

        log_audit(
            agent_name="pipeline",
            action="pipeline.start",
            metadata={"run_id": run_id, "run_number": self._run_count},
        )

        await self.bus.publish(
            Message(
                topic="pipeline.start",
                agent_source="pipeline",
                payload={"run_id": run_id},
                correlation_id=run_id,
                priority=2,
            )
        )

        try:
            # Stage 1: Scrape
            self.status = PipelineStatus.SCRAPING
            logger.info("[Stage 1/4] Scraping prices...")
            scrape_result = await self.scraper.run(
                medicine_names=medicine_names,
                platforms=platforms,
                max_concurrent=max_concurrent,
            )
            result["stages"]["scrape"] = scrape_result

            await self.bus.publish(
                Message(
                    topic="scrape.complete",
                    agent_source="scraper",
                    payload=scrape_result,
                    correlation_id=run_id,
                )
            )

            # Stage 2: Compliance Check
            self.status = PipelineStatus.CHECKING
            logger.info("[Stage 2/4] Running compliance checks...")
            compliance_result = await self.compliance.run()
            result["stages"]["compliance"] = compliance_result

            await self.bus.publish(
                Message(
                    topic="compliance.complete",
                    agent_source="compliance",
                    payload=compliance_result,
                    correlation_id=run_id,
                )
            )

            # Stage 3: Report
            self.status = PipelineStatus.REPORTING
            logger.info("[Stage 3/4] Generating report...")
            report_result = await self.reporter.run(report_type="daily_summary")
            result["stages"]["report"] = report_result

            await self.bus.publish(
                Message(
                    topic="report.ready",
                    agent_source="reporter",
                    payload=report_result,
                    correlation_id=run_id,
                )
            )

            # Stage 4: Alert
            self.status = PipelineStatus.ALERTING
            logger.info("[Stage 4/4] Dispatching alerts...")
            alert_result = await self.alert.run(severity_threshold="high")
            result["stages"]["alert"] = alert_result

            await self.bus.publish(
                Message(
                    topic="alert.complete",
                    agent_source="alert",
                    payload=alert_result,
                    correlation_id=run_id,
                )
            )

            # Pipeline complete
            self.status = PipelineStatus.COMPLETED
            duration_ms = int((time.time() - start_time) * 1000)
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            result["duration_ms"] = duration_ms
            result["status"] = "completed"

            logger.info(
                f"Pipeline run #{self._run_count} completed in {duration_ms}ms: "
                f"{compliance_result.get('violations', 0)} violations found"
            )

        except Exception as e:
            self.status = PipelineStatus.FAILED
            duration_ms = int((time.time() - start_time) * 1000)
            result["status"] = "failed"
            result["error"] = str(e)
            result["duration_ms"] = duration_ms

            logger.error(f"Pipeline run #{self._run_count} failed: {e}")

            await self.bus.publish(
                Message(
                    topic="pipeline.error",
                    agent_source="pipeline",
                    payload={"error": str(e), "run_id": run_id},
                    correlation_id=run_id,
                    priority=3,
                )
            )

        self.last_run = datetime.now(timezone.utc)
        self.last_result = result

        log_audit(
            agent_name="pipeline",
            action="pipeline.complete",
            output_data=result,
            duration_ms=result.get("duration_ms"),
        )

        return result

    async def run_incremental(self, platform: str, medicine_names: list[str] | None = None) -> dict:
        """Run an incremental scan for a single platform."""
        return await self.run_full_scan(
            medicine_names=medicine_names,
            platforms=[platform],
            max_concurrent=1,
        )

    def get_status(self) -> dict:
        """Get current pipeline status."""
        return {
            "status": self.status.value,
            "run_count": self._run_count,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "agents": {
                "scraper": self.scraper.get_status(),
                "compliance": self.compliance.get_status(),
                "reporter": self.reporter.get_status(),
                "alert": self.alert.get_status(),
            },
            "message_bus": self.bus.stats,
        }
