"""Reusable transport retry policies."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TransportRetryPolicy:
    """Define exponential backoff for transports."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    retryable_exceptions: tuple[type[BaseException], ...] = field(
        default_factory=lambda: (ConnectionError, TimeoutError)
    )
    retryable_status_codes: tuple[int, ...] = field(
        default_factory=lambda: (429, 500, 502, 503, 504)
    )

    def should_retry_status(self, status_code: int) -> bool:
        """Return whether a status code is retriable."""

        return status_code in self.retryable_status_codes

    def should_retry_exception(self, error: BaseException) -> bool:
        """Return whether an exception is retriable."""

        return isinstance(error, self.retryable_exceptions)

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the delay for a retry attempt."""

        if attempt < 1:
            raise ValueError("Attempt number must be at least 1.")

        delay = self.base_delay_seconds * (2 ** (attempt - 1))
        return float(min(delay, self.max_delay_seconds))
