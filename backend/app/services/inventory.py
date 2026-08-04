"""Inventory synchronization service."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.cache.redis import CacheBackend
from backend.app.core.exceptions import ServiceError
from backend.app.integrations.netbox.cache import NetBoxCacheKeys
from backend.app.integrations.netbox.service import NetBoxService
from backend.app.inventory.dto import InventorySnapshot
from backend.app.inventory.mapper import InventoryMapper
from backend.app.services.base import BaseService


@dataclass(slots=True)
class InventoryService(BaseService):
    """Synchronize canonical inventory from NetBox."""

    netbox_service: NetBoxService
    inventory_mapper: InventoryMapper
    cache: CacheBackend
    cache_keys: NetBoxCacheKeys = field(default_factory=NetBoxCacheKeys)
    cache_ttl_seconds: int = 300

    async def synchronize(self, *, force_refresh: bool = False) -> InventorySnapshot:
        """Synchronize inventory data from NetBox."""

        cache_key = self.cache_keys.inventory()
        if not force_refresh:
            cached_snapshot = await self.cache.get(cache_key)
            if cached_snapshot is not None:
                return InventorySnapshot.model_validate_json(
                    cached_snapshot.decode("utf-8")
                )

        try:
            dataset = await self.netbox_service.fetch_inventory_dataset()
            snapshot = self.inventory_mapper.to_snapshot(dataset)
            await self.cache.set(
                cache_key,
                snapshot.model_dump_json().encode("utf-8"),
                ttl_seconds=self.cache_ttl_seconds,
            )
            return snapshot
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ServiceError("Inventory synchronization failed.") from exc
