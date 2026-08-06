"""Job progress tracking and callback definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from backend.app.orchestration.progress import OrchestrationProgress

JobProgressCallback = Callable[["JobProgress"], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class JobProgress:
    """Immutable progress update for a job."""

    job_id: UUID
    step: str
    completed_steps: int
    total_steps: int
    percent: float
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_orchestration(
        cls, job_id: UUID, progress: OrchestrationProgress
    ) -> "JobProgress":
        """Create job progress from orchestration progress."""

        return cls(
            job_id=job_id,
            step=progress.step,
            completed_steps=progress.completed_steps,
            total_steps=progress.total_steps,
            percent=progress.percent,
            message=progress.message,
        )
