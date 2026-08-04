"""Discovery statistics tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class DiscoveryStatistics:
    """Track discovery execution metrics."""

    total_targets: int = 0
    processed_targets: int = 0
    discovered_targets: int = 0
    successful_targets: int = 0
    failed_targets: int = 0
    skipped_targets: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    def mark_started(self) -> None:
        """Reset the timer."""

        self.started_at = datetime.now(UTC)
        self.completed_at = None

    def mark_total(self, count: int) -> None:
        """Record the total number of targets."""

        self.total_targets = count

    def mark_processed(self) -> None:
        """Increment the processed target count."""

        self.processed_targets += 1

    def mark_discovered(self, count: int = 1) -> None:
        """Increment discovered targets."""

        self.discovered_targets += count

    def mark_success(self) -> None:
        """Increment successful targets."""

        self.successful_targets += 1

    def mark_failure(self) -> None:
        """Increment failed targets."""

        self.failed_targets += 1

    def mark_skipped(self) -> None:
        """Increment skipped targets."""

        self.skipped_targets += 1

    def mark_completed(self) -> None:
        """Record completion time."""

        self.completed_at = datetime.now(UTC)

    @property
    def duration_seconds(self) -> float | None:
        """Return the elapsed duration in seconds."""

        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()
