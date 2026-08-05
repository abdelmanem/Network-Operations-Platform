"""Collector execution state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.app.collectors.execution.progress import CollectorExecutionProgress
from backend.app.collectors.execution.status import CollectorExecutionStatus


@dataclass(slots=True)
class CollectorExecutionState:
    """Mutable state machine for collector runtime execution."""

    status: CollectorExecutionStatus = CollectorExecutionStatus.PENDING
    attempts: int = 0
    progress: CollectorExecutionProgress = field(
        default_factory=CollectorExecutionProgress.initial
    )
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    cancelled_at: datetime | None = None

    def mark_queued(self) -> None:
        """Transition to queued."""

        self._set_status(CollectorExecutionStatus.QUEUED)

    def mark_running(self) -> None:
        """Transition to running."""

        self.started_at = datetime.now(UTC)
        self._set_status(CollectorExecutionStatus.RUNNING)
        self.progress.advance("running", message="Collector execution started.")

    def mark_retrying(self, *, message: str | None = None) -> None:
        """Transition to retrying."""

        self._set_status(CollectorExecutionStatus.RETRYING)
        self.progress.advance("retrying", message=message)

    def mark_succeeded(self) -> None:
        """Transition to succeeded."""

        self.finished_at = datetime.now(UTC)
        self._set_status(CollectorExecutionStatus.SUCCEEDED)
        self.progress.advance("completed", message="Collector execution completed.")

    def mark_failed(self, message: str) -> None:
        """Transition to failed."""

        self.finished_at = datetime.now(UTC)
        self.error_message = message
        self._set_status(CollectorExecutionStatus.FAILED)
        self.progress.advance("failed", message=message)

    def mark_cancelled(self, message: str | None = None) -> None:
        """Transition to cancelled."""

        self.finished_at = datetime.now(UTC)
        self.cancelled_at = self.finished_at
        self.error_message = message
        self._set_status(CollectorExecutionStatus.CANCELLED)
        self.progress.advance("cancelled", message=message)

    def mark_timed_out(self, message: str | None = None) -> None:
        """Transition to timed out."""

        self.finished_at = datetime.now(UTC)
        self.error_message = message
        self._set_status(CollectorExecutionStatus.TIMED_OUT)
        self.progress.advance("timed_out", message=message)

    def increment_attempts(self) -> None:
        """Increment the attempt counter."""

        self.attempts += 1

    def _set_status(self, status: CollectorExecutionStatus) -> None:
        self.status = status
