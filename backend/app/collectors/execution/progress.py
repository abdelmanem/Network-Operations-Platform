"""Collector execution progress models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class CollectorExecutionProgress:
    """Track progress for a collector job."""

    total_steps: int = 4
    completed_steps: int = 0
    current_step: str = "pending"
    message: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def percent_complete(self) -> float:
        """Return the completion percentage."""

        if self.total_steps <= 0:
            return 0.0
        return min(100.0, (self.completed_steps / self.total_steps) * 100.0)

    def advance(self, step: str, *, message: str | None = None) -> None:
        """Advance the progress tracker by one step."""

        self.completed_steps = min(self.total_steps, self.completed_steps + 1)
        self.current_step = step
        self.message = message
        self.updated_at = datetime.now(UTC)

    @classmethod
    def initial(cls) -> CollectorExecutionProgress:
        """Return a default progress model."""

        return cls()
