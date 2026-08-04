"""Transport rate limiting."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class RateLimiter:
    """Token bucket rate limiter."""

    tokens_per_second: float
    capacity: float | None = None
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        if self.tokens_per_second <= 0:
            raise ValueError("Token rate must be positive.")

        capacity = (
            self.capacity if self.capacity is not None else self.tokens_per_second
        )
        if capacity <= 0:
            raise ValueError("Capacity must be positive.")

        self.capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(
            self.capacity or self.tokens_per_second,
            self._tokens + elapsed * self.tokens_per_second,
        )

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until the requested tokens are available."""

        if tokens <= 0:
            raise ValueError("Token count must be positive.")

        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                await asyncio.sleep(deficit / self.tokens_per_second)

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Attempt to acquire tokens without waiting."""

        if tokens <= 0:
            raise ValueError("Token count must be positive.")

        self._refill()
        if self._tokens < tokens:
            return False

        self._tokens -= tokens
        return True
