"""Discovery engine entrypoint."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.discovery.context import DiscoveryContext
from backend.app.discovery.pipeline import DiscoveryPipeline
from backend.app.discovery.registry import DiscoveryRegistry
from backend.app.discovery.statistics import DiscoveryStatistics
from backend.app.snapshot.entities import InventorySnapshot


@dataclass(slots=True)
class DiscoveryRunResult:
    """Result of a discovery run."""

    pipeline_name: str
    snapshot: InventorySnapshot
    statistics: DiscoveryStatistics


@dataclass(slots=True)
class DiscoveryEngine:
    """Resolve and execute discovery pipelines."""

    registry: DiscoveryRegistry

    async def run(self, context: DiscoveryContext) -> DiscoveryRunResult:
        """Run the discovery pipeline associated with the context."""

        pipeline = self._resolve_pipeline(context.pipeline_name)
        snapshot = await pipeline.execute(context)
        return DiscoveryRunResult(
            pipeline_name=context.pipeline_name,
            snapshot=snapshot,
            statistics=pipeline.statistics,
        )

    def _resolve_pipeline(self, pipeline_name: str) -> DiscoveryPipeline:
        pipeline = self.registry.get(pipeline_name)
        if not isinstance(pipeline, DiscoveryPipeline):
            raise TypeError(f"Discovery registry entry '{pipeline_name}' is invalid.")
        return pipeline
