"""Transport circuit breaker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class CircuitBreakerState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class CircuitBreaker:
    """Track failure thresholds for transport operations."""

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_success_threshold: int = 1
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    half_open_success_count: int = 0
    opened_at: datetime | None = None

    def allow_request(self) -> bool:
        """Return whether a request may proceed."""

        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            if self.opened_at is None:
                return False
            if datetime.now(UTC) - self.opened_at >= timedelta(
                seconds=self.recovery_timeout_seconds
            ):
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_success_count = 0
                return True
            return False

        return True

    def record_success(self) -> None:
        """Record a successful operation."""

        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_success_count += 1
            if self.half_open_success_count >= self.half_open_success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.half_open_success_count = 0

    def record_failure(self) -> None:
        """Record a failed operation."""

        self.failure_count += 1
        self.half_open_success_count = 0
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.opened_at = datetime.now(UTC)
