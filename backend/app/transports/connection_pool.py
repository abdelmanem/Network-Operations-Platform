"""Reusable transport connection pool."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.app.transports.session import TransportSession


@dataclass(slots=True)
class ConnectionPool:
    """Cache and reuse transport sessions."""

    max_size: int = 32
    _sessions: dict[str, TransportSession] = field(default_factory=dict)
    _locks: dict[str, asyncio.Lock] = field(default_factory=dict)

    def _lock_for(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    async def get_or_create(
        self,
        key: str,
        factory: Callable[[], TransportSession],
    ) -> TransportSession:
        """Return a cached session or create a new one."""

        lock = self._lock_for(key)
        async with lock:
            session = self._sessions.get(key)
            if session is not None:
                return session

            if len(self._sessions) >= self.max_size:
                raise RuntimeError("Connection pool is full.")

            session = factory()
            await session.open()
            self._sessions[key] = session
            return session

    async def release(self, key: str) -> None:
        """Release a session from the pool."""

        lock = self._lock_for(key)
        async with lock:
            session = self._sessions.pop(key, None)
            if session is not None:
                await session.close()

    async def close_all(self) -> None:
        """Close every pooled session."""

        for key in tuple(self._sessions):
            await self.release(key)
