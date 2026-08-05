"""Orchestration progress tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class OrchestrationProgress:
    """Immutable progress update."""

    step: str
    completed_steps: int
    total_steps: int
    message: str | None = None
    percent: float = 0.0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        step: str,
        completed_steps: int,
        total_steps: int,
        *,
        message: str | None = None,
    ) -> OrchestrationProgress:
        """Create a progress update."""

        percent = 100.0 if total_steps == 0 else (completed_steps / total_steps) * 100
        return cls(
            step=step,
            completed_steps=completed_steps,
            total_steps=total_steps,
            message=message,
            percent=round(percent, 2),
        )
