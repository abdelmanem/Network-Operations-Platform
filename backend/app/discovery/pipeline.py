"""Discovery pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.context import DiscoveryContext
from backend.app.discovery.filters import DiscoveryFilter
from backend.app.discovery.statistics import DiscoveryStatistics
from backend.app.snapshot.entities import InventorySnapshot
from backend.app.snapshot.mapper import SnapshotMapper
from backend.app.snapshot.repository import SnapshotRepository
from backend.app.snapshot.validation import validate_snapshot_integrity


@dataclass(slots=True)
class DiscoveryPipeline:
    """Orchestrate collection, normalization, and snapshot persistence."""

    collector_registry: CollectorRegistry
    snapshot_repository: SnapshotRepository | None = None
    snapshot_mapper: SnapshotMapper = field(default_factory=SnapshotMapper)
    filters: tuple[DiscoveryFilter, ...] = ()
    statistics: DiscoveryStatistics = field(default_factory=DiscoveryStatistics)

    async def execute(self, context: DiscoveryContext) -> InventorySnapshot:
        """Run discovery for a single target."""

        self.statistics.mark_total(1)
        self.statistics.mark_started()
        self.statistics.mark_processed()

        if self.filters and not all(
            filter_.matches(context) for filter_ in self.filters
        ):
            self.statistics.mark_skipped()
            self.statistics.mark_completed()
            return InventorySnapshot.empty()

        collectors = self.collector_registry.select(context.required_capabilities)
        snapshots: list[InventorySnapshot] = []
        for collector in collectors:
            collector_context = collector.build_context(context)
            await collector.health_check(collector_context)
            discovered_targets = await collector.discover(collector_context)
            raw_result = await collector.collect(
                collector_context,
                discovered_targets=discovered_targets,
            )
            snapshot = await collector.normalize(
                collector_context,
                raw_result,
                discovered_targets=discovered_targets,
            )
            snapshots.append(snapshot)
            self.statistics.mark_discovered()

        snapshot = InventorySnapshot.merge(*snapshots)
        snapshot_model = self.snapshot_mapper.to_model(snapshot)
        validate_snapshot_integrity(snapshot_model)

        if self.snapshot_repository is not None:
            await self.snapshot_repository.save(snapshot_model)

        self.statistics.mark_success()
        self.statistics.mark_completed()
        return snapshot
