"""Transport metrics models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class TransportMetrics:
    """Track transport session counters."""

    attempts: int = 0
    successes: int = 0
    failures: int = 0
    opened_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None

    def record_attempt(self) -> None:
        """Record an attempted transport operation."""

        self.attempts += 1
        if self.opened_at is None:
            self.opened_at = datetime.now(UTC)

    def record_success(self) -> None:
        """Record a successful transport operation."""

        self.successes += 1
        self.last_success_at = datetime.now(UTC)

    def record_failure(self) -> None:
        """Record a failed transport operation."""

        self.failures += 1
        self.last_failure_at = datetime.now(UTC)

    def as_dict(self) -> dict[str, object]:
        """Return a serializable metrics mapping."""

        return {
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "last_success_at": (
                self.last_success_at.isoformat() if self.last_success_at else None
            ),
            "last_failure_at": (
                self.last_failure_at.isoformat() if self.last_failure_at else None
            ),
        }
