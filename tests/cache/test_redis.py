import pytest
from backend.app.cache.redis import (
    InMemoryCache,
    ResilientCache,
    build_cache_key,
    cache_result,
)


class FailingCache:
    async def get(self, key: str) -> bytes | None:
        raise RuntimeError("redis unavailable")

    async def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        raise RuntimeError("redis unavailable")

    async def delete(self, key: str) -> None:
        raise RuntimeError("redis unavailable")

    async def clear(self) -> None:
        raise RuntimeError("redis unavailable")


@pytest.mark.anyio
async def test_resilient_cache_falls_back_to_memory() -> None:
    cache = ResilientCache(primary=FailingCache(), fallback=InMemoryCache())
    key = build_cache_key("inventory", "snapshot")

    await cache.set(key, b"payload", ttl_seconds=30)
    assert await cache.get(key) == b"payload"


@pytest.mark.anyio
async def test_cache_result_uses_cached_value() -> None:
    cache = InMemoryCache()
    calls = {"count": 0}

    @cache_result(
        cache,
        key_builder=lambda value: build_cache_key("demo", value),
        dumps=lambda value: value.encode("utf-8"),
        loads=lambda payload: payload.decode("utf-8"),
    )
    async def compute(value: str) -> str:
        calls["count"] += 1
        return value.upper()

    first = await compute("alpha")
    second = await compute("alpha")

    assert first == "ALPHA"
    assert second == "ALPHA"
    assert calls["count"] == 1
