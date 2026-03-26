"""Abstract base class for all MedGuard AI agents."""

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum

from src.security.audit_log import log_audit
from src.utils.logger import get_logger


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BaseAgent(ABC):
    """Base class providing lifecycle, audit logging, and status tracking."""

    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"agent.{name}")
        self.status = AgentStatus.IDLE
        self.last_run: datetime | None = None
        self.last_duration_ms: int | None = None
        self.run_count = 0
        self.error_count = 0

    @abstractmethod
    async def execute(self, **kwargs) -> dict:
        """Execute the agent's main task. Must be implemented by subclasses."""
        ...

    async def run(self, **kwargs) -> dict:
        """Run the agent with lifecycle management and audit logging."""
        self.status = AgentStatus.RUNNING
        self.run_count += 1
        start_time = time.time()
        run_id = str(uuid.uuid4())

        self.logger.info(f"Agent '{self.name}' starting run #{self.run_count} (id={run_id[:8]})")

        log_audit(
            agent_name=self.name,
            action=f"{self.name}.start",
            metadata={"run_id": run_id, "run_number": self.run_count, "kwargs": str(kwargs)},
        )

        try:
            result = await self.execute(**kwargs)
            duration_ms = int((time.time() - start_time) * 1000)
            self.status = AgentStatus.COMPLETED
            self.last_run = datetime.now(timezone.utc)
            self.last_duration_ms = duration_ms

            self.logger.info(f"Agent '{self.name}' completed in {duration_ms}ms")

            log_audit(
                agent_name=self.name,
                action=f"{self.name}.complete",
                metadata={"run_id": run_id, "duration_ms": duration_ms},
                output_data=result,
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.status = AgentStatus.FAILED
            self.error_count += 1

            self.logger.error(f"Agent '{self.name}' failed after {duration_ms}ms: {e}")

            log_audit(
                agent_name=self.name,
                action=f"{self.name}.error",
                metadata={"run_id": run_id, "error": str(e), "duration_ms": duration_ms},
                duration_ms=duration_ms,
            )
            raise

    def get_status(self) -> dict:
        """Return agent status summary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_duration_ms": self.last_duration_ms,
            "run_count": self.run_count,
            "error_count": self.error_count,
        }
