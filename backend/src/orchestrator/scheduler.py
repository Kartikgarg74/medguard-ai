"""APScheduler wrapper for recurring agent tasks."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class JobScheduler:
    """Async-friendly scheduler for recurring agent tasks."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._jobs: dict[str, str] = {}

    def add_cron_job(
        self,
        func,
        hour: int,
        minute: int = 0,
        timezone: str = "Asia/Kolkata",
        job_id: str = "",
        day_of_week: str = "mon-fri",
    ):
        """Add a cron-scheduled job."""
        job_id = job_id or f"cron_{func.__name__}"
        self.scheduler.add_job(
            func,
            CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=day_of_week,
                timezone=timezone,
            ),
            id=job_id,
            replace_existing=True,
        )
        self._jobs[job_id] = f"cron({hour}:{minute:02d} {day_of_week})"
        logger.info(f"Scheduled cron job '{job_id}': {hour}:{minute:02d} {day_of_week}")

    def add_interval_job(
        self,
        func,
        hours: int = 0,
        minutes: int = 0,
        job_id: str = "",
    ):
        """Add an interval-scheduled job."""
        job_id = job_id or f"interval_{func.__name__}"
        self.scheduler.add_job(
            func,
            IntervalTrigger(hours=hours, minutes=minutes),
            id=job_id,
            replace_existing=True,
        )
        interval_str = f"{hours}h{minutes}m" if hours else f"{minutes}m"
        self._jobs[job_id] = f"every {interval_str}"
        logger.info(f"Scheduled interval job '{job_id}': every {interval_str}")

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info(f"Scheduler started with {len(self._jobs)} jobs")

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler shut down")

    @property
    def status(self) -> dict:
        return {
            "running": self.scheduler.running,
            "jobs": self._jobs,
            "job_count": len(self._jobs),
        }
