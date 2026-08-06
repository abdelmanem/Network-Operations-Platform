"""Redis cache abstraction with graceful fallback support."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Protocol, cast

from backend.app.core.exceptions import ApplicationError

_redis_import_error: Exception | None = None

try:
    import redis.asyncio as redis_asyncio
except ImportError as exc:  # pragma: no cover - dependency is present in project
    redis_asyncio = None  # type: ignore[assignment]
    _redis_import_error = exc


class CacheError(ApplicationError):
    """Raised when cache operations fail."""


class CacheBackend(Protocol):
    """Protocol for cache backends."""

    async def get(self, key: str) -> bytes | None:
        """Return a cached payload if present."""

    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        """Store a cached payload."""

    async def delete(self, key: str) -> None:
        """Remove a cached payload."""

    async def clear(self) -> None:
        """Remove all cached payloads."""


def build_cache_key(namespace: str, *parts: object) -> str:
    """Build a deterministic cache key."""

    encoded_parts = [namespace]
    encoded_parts.extend(str(part) for part in parts)
    return ":".join(encoded_parts)


@dataclass(slots=True)
class InMemoryCache:
    """In-memory cache implementation with TTL support."""

    _items: dict[str, tuple[bytes, float | None]] = field(default_factory=dict)

    async def get(self, key: str) -> bytes | None:
        """Return a cached payload if present."""

        item = self._items.get(key)
        if item is None:
            return None

        payload, expires_at = item
        if expires_at is not None and time.monotonic() >= expires_at:
            self._items.pop(key, None)
            return None

        return payload

    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        """Store a cached payload."""

        expires_at = None
        if ttl_seconds is not None:
            expires_at = time.monotonic() + ttl_seconds
        self._items[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        """Remove a cached payload."""

        self._items.pop(key, None)

    async def clear(self) -> None:
        """Remove all cached payloads."""

        self._items.clear()


@dataclass(slots=True)
class RedisCache:
    """Redis-backed cache implementation."""

    client: Any
    key_prefix: str = "nop"

    @classmethod
    def from_url(cls, url: str, key_prefix: str = "nop") -> RedisCache:
        """Create a Redis cache from a URL."""

        if redis_asyncio is None:  # pragma: no cover - defensive guard
            raise CacheError("Redis support is not available.") from _redis_import_error

        return cls(
            client=cast(Any, redis_asyncio).from_url(url, decode_responses=False),
            key_prefix=key_prefix,
        )

    def _key(self, key: str) -> str:
        return build_cache_key(self.key_prefix, key)

    async def get(self, key: str) -> bytes | None:
        """Return a cached payload if present."""

        return cast(bytes | None, await self.client.get(self._key(key)))

    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        """Store a cached payload."""

        namespaced_key = self._key(key)
        if ttl_seconds is None:
            await self.client.set(namespaced_key, value)
            return

        await self.client.set(namespaced_key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        """Remove a cached payload."""

        await self.client.delete(self._key(key))

    async def clear(self) -> None:
        """Remove all cached payloads."""

        await self.client.flushdb()


@dataclass(slots=True)
class ResilientCache:
    """Cache wrapper that falls back when the primary cache fails."""

    primary: CacheBackend
    fallback: CacheBackend = field(default_factory=InMemoryCache)
    logger: logging.Logger | None = None
    _degraded: bool = False

    def _log_degraded(self, error: Exception) -> None:
        if self.logger is not None:
            self.logger.warning(
                "Redis cache unavailable; falling back to memory cache.",
                exc_info=True,
            )

    async def get(self, key: str) -> bytes | None:
        """Return a cached payload if present."""

        if self._degraded:
            return await self.fallback.get(key)

        try:
            return await self.primary.get(key)
        except Exception as exc:  # pragma: no cover - defensive guard
            self._degraded = True
            self._log_degraded(exc)
            return await self.fallback.get(key)

    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        """Store a cached payload."""

        if self._degraded:
            await self.fallback.set(key, value, ttl_seconds)
            return

        try:
            await self.primary.set(key, value, ttl_seconds)
        except Exception as exc:  # pragma: no cover - defensive guard
            self._degraded = True
            self._log_degraded(exc)
            await self.fallback.set(key, value, ttl_seconds)

    async def delete(self, key: str) -> None:
        """Remove a cached payload."""

        if self._degraded:
            await self.fallback.delete(key)
            return

        try:
            await self.primary.delete(key)
        except Exception as exc:  # pragma: no cover - defensive guard
            self._degraded = True
            self._log_degraded(exc)
            await self.fallback.delete(key)

    async def clear(self) -> None:
        """Remove all cached payloads."""

        if self._degraded:
            await self.fallback.clear()
            return

        try:
            await self.primary.clear()
        except Exception as exc:  # pragma: no cover - defensive guard
            self._degraded = True
            self._log_degraded(exc)
            await self.fallback.clear()


def build_cache_backend(
    redis_url: str,
    *,
    key_prefix: str = "nop",
    logger: logging.Logger | None = None,
) -> CacheBackend:
    """Build a cache backend that survives Redis outages."""

    if not redis_url:
        return InMemoryCache()

    return ResilientCache(
        primary=RedisCache.from_url(redis_url, key_prefix=key_prefix),
        fallback=InMemoryCache(),
        logger=logger,
    )


def cache_result[
    **P, TValue
](
    cache: CacheBackend,
    *,
    key_builder: Callable[P, str],
    ttl_seconds: int | None = None,
    dumps: Callable[[TValue], bytes],
    loads: Callable[[bytes], TValue],
) -> Callable[[Callable[P, Awaitable[TValue]]], Callable[P, Awaitable[TValue]]]:
    """Cache the result of an async function."""

    def decorator(
        func: Callable[P, Awaitable[TValue]],
    ) -> Callable[P, Awaitable[TValue]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> TValue:
            key = key_builder(*args, **kwargs)
            cached = await cache.get(key)
            if cached is not None:
                return loads(cached)

            result = await func(*args, **kwargs)
            await cache.set(key, dumps(result), ttl_seconds)
            return result

        return wrapper

    return decorator
