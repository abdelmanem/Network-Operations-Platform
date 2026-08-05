"""Discovery coordination helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.app.collectors.execution.result import CollectorExecutionResult
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.job import CollectorJob
from backend.app.snapshot.entities import InventorySnapshot


class CollectorRuntimeProtocol(Protocol):
    """Runtime protocol consumed by orchestration."""

    async def start(self) -> None:
        """Start runtime services."""

    async def stop(self) -> None:
        """Stop runtime services."""

    async def submit(
        self,
        context: CollectorRuntimeContext,
        *,
        priority: int = 0,
    ) -> CollectorJob:
        """Submit a collector context."""

    async def run_job(self, job: CollectorJob) -> CollectorExecutionResult:
        """Run one scheduled collector job."""


@dataclass(slots=True)
class DiscoveryCoordinator:
    """Coordinate collector runtime jobs and live snapshot aggregation."""

    collector_runtime: CollectorRuntimeProtocol

    async def collect(
        self,
        contexts: tuple[CollectorRuntimeContext, ...],
    ) -> tuple[InventorySnapshot, tuple[CollectorExecutionResult, ...]]:
        """Execute collector jobs and merge live snapshots."""

        snapshots: list[InventorySnapshot] = []
        results: list[CollectorExecutionResult] = []
        await self.collector_runtime.start()
        try:
            for context in contexts:
                job = await self.collector_runtime.submit(context)
                result = await self.collector_runtime.run_job(job)
                results.append(result)
                if result.snapshot is not None:
                    snapshots.append(result.snapshot)
        finally:
            await self.collector_runtime.stop()
        return InventorySnapshot.merge(*snapshots), tuple(results)
