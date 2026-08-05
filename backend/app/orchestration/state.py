"""Orchestration run state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class OrchestrationStatus(StrEnum):
    """Lifecycle states for orchestration runs."""

    PENDING = "pending"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class OrchestrationState:
    """Mutable state machine for one orchestration run."""

    status: OrchestrationStatus = OrchestrationStatus.PENDING
    attempts: int = 0
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def mark_running(self) -> None:
        """Mark the run as running."""

        self.status = OrchestrationStatus.RUNNING
        self.started_at = self.started_at or datetime.now(UTC)
        self._touch()

    def mark_retrying(self, message: str) -> None:
        """Mark the run as retrying."""

        self.status = OrchestrationStatus.RETRYING
        self.message = message
        self._touch()

    def mark_succeeded(self) -> None:
        """Mark the run as successful."""

        self.status = OrchestrationStatus.SUCCEEDED
        self.finished_at = datetime.now(UTC)
        self._touch()

    def mark_failed(self, message: str) -> None:
        """Mark the run as failed."""

        self.status = OrchestrationStatus.FAILED
        self.message = message
        self.finished_at = datetime.now(UTC)
        self._touch()

    def mark_cancelled(self, message: str) -> None:
        """Mark the run as cancelled."""

        self.status = OrchestrationStatus.CANCELLED
        self.message = message
        self.finished_at = datetime.now(UTC)
        self._touch()

    def increment_attempts(self) -> None:
        """Increment run attempts."""

        self.attempts += 1
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
