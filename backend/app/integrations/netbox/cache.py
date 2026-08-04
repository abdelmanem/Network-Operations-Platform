"""NetBox response cache helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from backend.app.cache.redis import CacheBackend, build_cache_key
from backend.app.integrations.netbox.endpoints import NetBoxEndpoint


@dataclass(frozen=True, slots=True)
class NetBoxCacheKeys:
    """Cache key builder for NetBox resources."""

    namespace: str = "netbox"

    def health(self) -> str:
        """Return the cache key for the health endpoint."""

        return build_cache_key(self.namespace, "health")

    def collection(
        self,
        endpoint: NetBoxEndpoint | str,
        params: Mapping[str, object] | None = None,
    ) -> str:
        """Return the cache key for a resource collection."""

        normalized_params = tuple(
            f"{key}={value}" for key, value in sorted((params or {}).items())
        )
        return build_cache_key(
            self.namespace, "collection", str(endpoint), *normalized_params
        )

    def inventory(self) -> str:
        """Return the cache key for the inventory snapshot."""

        return build_cache_key(self.namespace, "inventory")


@dataclass(slots=True)
class NetBoxResponseCache:
    """Cache wrapper for NetBox responses."""

    backend: CacheBackend
    keys: NetBoxCacheKeys = field(default_factory=NetBoxCacheKeys)
    default_ttl_seconds: int = 300

    async def get_json(self, key: str) -> dict[str, object] | None:
        """Return a cached JSON payload."""

        payload = await self.backend.get(key)
        if payload is None:
            return None

        import json

        return cast(dict[str, object], json.loads(payload.decode("utf-8")))

    async def set_json(
        self,
        key: str,
        payload: Mapping[str, object],
        ttl_seconds: int | None = None,
    ) -> None:
        """Cache a JSON payload."""

        import json

        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        await self.backend.set(key, encoded, ttl_seconds or self.default_ttl_seconds)

    async def invalidate_collection(
        self,
        endpoint: NetBoxEndpoint | str,
        params: Mapping[str, object] | None = None,
    ) -> None:
        """Invalidate a cached collection."""

        await self.backend.delete(self.keys.collection(endpoint, params))

    async def invalidate_inventory(self) -> None:
        """Invalidate the cached inventory snapshot."""

        await self.backend.delete(self.keys.inventory())
