"""Job lifecycle state and status definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class JobStatus(StrEnum):
    """Lifecycle states for job execution."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(slots=True)
class JobState:
    """Mutable state machine for one job."""

    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def mark_queued(self) -> None:
        """Mark the job as queued."""

        self.status = JobStatus.QUEUED
        self.queued_at = self.queued_at or datetime.now(UTC)
        self._touch()

    def mark_running(self) -> None:
        """Mark the job as running."""

        self.status = JobStatus.RUNNING
        self.started_at = self.started_at or datetime.now(UTC)
        self._touch()

    def mark_retrying(self, message: str) -> None:
        """Mark the job as retrying."""

        self.status = JobStatus.RETRYING
        self.message = message
        self._touch()

    def mark_completed(self, message: str | None = None) -> None:
        """Mark the job as completed."""

        self.status = JobStatus.COMPLETED
        self.message = message
        self.finished_at = datetime.now(UTC)
        self._touch()

    def mark_failed(self, message: str) -> None:
        """Mark the job as failed."""

        self.status = JobStatus.FAILED
        self.message = message
        self.finished_at = datetime.now(UTC)
        self._touch()

    def mark_cancelled(self, message: str | None = None) -> None:
        """Mark the job as cancelled."""

        self.status = JobStatus.CANCELLED
        self.message = message
        self.finished_at = datetime.now(UTC)
        self._touch()

    def mark_timed_out(self, message: str | None = None) -> None:
        """Mark the job as timed out."""

        self.status = JobStatus.TIMED_OUT
        self.message = message
        self.finished_at = datetime.now(UTC)
        self._touch()

    def increment_attempts(self) -> None:
        """Increment the job attempt counter."""

        self.attempts += 1
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
