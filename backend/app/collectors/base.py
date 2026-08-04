"""Abstract collector SDK."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.app.collectors.context import CollectorContext
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryTarget
from backend.app.snapshot.entities import InventorySnapshot


@dataclass(slots=True)
class BaseCollector(ABC):
    """Base class for all collectors."""

    name: str
    capabilities: frozenset[CollectorCapability]

    @abstractmethod
    async def health_check(self, context: CollectorContext) -> None:
        """Validate collector reachability."""

    @abstractmethod
    async def discover(self, context: CollectorContext) -> tuple[DiscoveryTarget, ...]:
        """Discover downstream targets."""

    @abstractmethod
    async def collect(
        self,
        context: CollectorContext,
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> dict[str, object]:
        """Collect raw data from the target."""

    @abstractmethod
    async def normalize(
        self,
        context: CollectorContext,
        raw_payload: dict[str, object],
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> InventorySnapshot:
        """Normalize raw payloads into immutable snapshots."""

    @abstractmethod
    async def close(self) -> None:
        """Release collector resources."""

    def build_context(self, discovery_context: object) -> CollectorContext:
        """Build a collector-specific context."""

        from backend.app.discovery.context import DiscoveryContext

        if not isinstance(discovery_context, DiscoveryContext):
            raise TypeError("Discovery context is invalid.")
        return CollectorContext(
            target=discovery_context.target,
            capabilities=self.capabilities,
            run_id=discovery_context.run_id,
            discovered_at=discovery_context.started_at,
            metadata=dict(discovery_context.metadata),
        )
