"""Job models and request definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.events.interfaces import EventPublisher
from backend.app.jobs.cancellation import CancellationToken as JobCancellationToken
from backend.app.jobs.progress import JobProgressCallback
from backend.app.jobs.state import JobState
from backend.app.orchestration.context import (
    CancellationToken as OrchestrationCancellationToken,
)
from backend.app.orchestration.context import (
    OrchestrationContext,
)


@dataclass(frozen=True, slots=True)
class JobRequest:
    """Immutable request for creating a job."""

    context: OrchestrationContext
    priority: int = 0
    timeout_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class JobStateSnapshot:
    """Immutable snapshot of job state for history."""

    status: str
    attempts: int
    message: str | None
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime

    @classmethod
    def from_state(cls, state: JobState) -> JobStateSnapshot:
        return cls(
            status=state.status.value,
            attempts=state.attempts,
            message=state.message,
            created_at=state.created_at,
            queued_at=state.queued_at,
            started_at=state.started_at,
            finished_at=state.finished_at,
            updated_at=state.updated_at,
        )


@dataclass(slots=True)
class JobHistoryRecord:
    """Immutable job history record."""

    id: UUID
    request: JobRequest
    state: JobStateSnapshot
    result: dict[str, object] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class JobSubmissionResult:
    """Result returned when a job is submitted."""

    job: Job
    queued: bool


@dataclass(slots=True)
class Job:
    """One asynchronous orchestration job."""

    request: JobRequest
    id: UUID = field(default_factory=uuid4)
    state: JobState = field(default_factory=JobState)
    history: list[JobHistoryRecord] = field(default_factory=list)
    progress_callback: JobProgressCallback | None = None
    event_publisher: EventPublisher | None = None
    cancellation_token: JobCancellationToken | OrchestrationCancellationToken = field(
        default_factory=JobCancellationToken
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def cancel(self, reason: str = "Job cancelled.") -> None:
        """Request cancellation of the job."""

        self.cancellation_token.cancel(reason)
        self.state.mark_cancelled(reason)

    def record_history(self, result: dict[str, object] | None = None) -> None:
        """Append an immutable history record for this job."""

        self.history.append(
            JobHistoryRecord(
                id=uuid4(),
                request=self.request,
                state=JobStateSnapshot.from_state(self.state),
                result={} if result is None else dict(result),
            )
        )
