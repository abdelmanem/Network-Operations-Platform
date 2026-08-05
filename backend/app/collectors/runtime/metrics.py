"""Collector runtime metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class CollectorRuntimeMetrics:
    """Track collector runtime statistics."""

    submitted: int = 0
    started: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    retried: int = 0
    timed_out: int = 0
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    total_duration_seconds: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def record_submitted(self) -> None:
        """Increment submitted jobs."""

        self.submitted += 1
        self.updated_at = datetime.now(UTC)

    def record_started(self) -> None:
        """Increment started jobs."""

        self.started += 1
        self.last_started_at = datetime.now(UTC)
        self.updated_at = self.last_started_at

    def record_succeeded(self, duration_seconds: float) -> None:
        """Increment succeeded jobs."""

        self.succeeded += 1
        self.last_finished_at = datetime.now(UTC)
        self.total_duration_seconds += duration_seconds
        self.updated_at = self.last_finished_at

    def record_failed(self) -> None:
        """Increment failed jobs."""

        self.failed += 1
        self.last_finished_at = datetime.now(UTC)
        self.updated_at = self.last_finished_at

    def record_cancelled(self) -> None:
        """Increment cancelled jobs."""

        self.cancelled += 1
        self.last_finished_at = datetime.now(UTC)
        self.updated_at = self.last_finished_at

    def record_retry(self) -> None:
        """Increment retry attempts."""

        self.retried += 1
        self.updated_at = datetime.now(UTC)

    def record_timed_out(self) -> None:
        """Increment timed out jobs."""

        self.timed_out += 1
        self.last_finished_at = datetime.now(UTC)
        self.updated_at = self.last_finished_at

    @property
    def success_rate(self) -> float:
        """Return the success ratio."""

        finished = self.succeeded + self.failed + self.cancelled + self.timed_out
        if finished <= 0:
            return 0.0
        return self.succeeded / finished
