from datetime import UTC, datetime

import pytest
from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryContext, DiscoveryTarget
from backend.app.discovery.pipeline import DiscoveryPipeline
from backend.app.snapshot.entities import DeviceSnapshot, InventorySnapshot


class InMemorySnapshotRepository:
    def __init__(self) -> None:
        self.saved: list[object] = []

    async def save(self, snapshot: object) -> None:
        self.saved.append(snapshot)

    async def get(self, snapshot_id: object) -> object | None:
        return None

    async def list(self) -> tuple[object, ...]:
        return tuple(self.saved)

    async def delete(self, snapshot_id: object) -> None:
        return None

    async def clear(self) -> None:
        self.saved.clear()


class DummyCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        return None

    async def discover(self, context: CollectorContext) -> tuple[DiscoveryTarget, ...]:
        return ()

    async def collect(
        self,
        context: CollectorContext,
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> dict[str, object]:
        return {"target": context.target.identifier}

    async def normalize(
        self,
        context: CollectorContext,
        raw_payload: dict[str, object],
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> InventorySnapshot:
        return InventorySnapshot(
            devices=(
                DeviceSnapshot(
                    device_id=context.target.identifier,
                    name=str(raw_payload["target"]),
                    captured_at=datetime.now(UTC),
                ),
            ),
            captured_at=datetime.now(UTC),
        )

    async def close(self) -> None:
        return None


@pytest.mark.anyio
async def test_discovery_pipeline_collects_and_persists_snapshot() -> None:
    registry = CollectorRegistry()
    collector = DummyCollector(
        name="dummy",
        capabilities=frozenset({CollectorCapability.INTERFACES}),
    )
    registry.register(collector)
    repository = InMemorySnapshotRepository()
    pipeline = DiscoveryPipeline(
        collector_registry=registry,
        snapshot_repository=repository,
    )
    context = DiscoveryContext(
        target=DiscoveryTarget(
            identifier="device-1",
            address="10.0.0.1",
            capabilities=frozenset({CollectorCapability.INTERFACES}),
        ),
        required_capabilities=frozenset({CollectorCapability.INTERFACES}),
    )

    snapshot = await pipeline.execute(context)

    assert snapshot.devices[0].device_id == "device-1"
    assert len(repository.saved) == 1
