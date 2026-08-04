"""Reusable retry policy for NetBox requests."""

from __future__ import annotations

from dataclasses import dataclass, field

RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Define exponential backoff behavior for retriable requests."""

    max_attempts: int = 4
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    retryable_status_codes: tuple[int, ...] = field(
        default_factory=lambda: RETRYABLE_STATUS_CODES
    )

    def should_retry(self, status_code: int) -> bool:
        """Return whether a status code is retriable."""

        return status_code in self.retryable_status_codes

    def delay_for_attempt(
        self,
        attempt: int,
        *,
        retry_after_seconds: float | None = None,
    ) -> float:
        """Compute the delay for a retry attempt."""

        if attempt < 1:
            raise ValueError("Attempt number must be at least 1.")

        delay = min(
            self.base_delay_seconds * (2 ** (attempt - 1)),
            self.max_delay_seconds,
        )
        if retry_after_seconds is not None:
            delay = max(delay, retry_after_seconds)
        return float(delay)
