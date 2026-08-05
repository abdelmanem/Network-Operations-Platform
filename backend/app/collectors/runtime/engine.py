"""Collector runtime engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.collectors.execution.result import CollectorExecutionResult
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.dispatcher import CollectorDispatcher
from backend.app.collectors.runtime.job import CollectorJob
from backend.app.collectors.runtime.lifecycle import CollectorRuntimeLifecycle
from backend.app.collectors.runtime.metrics import CollectorRuntimeMetrics
from backend.app.collectors.runtime.scheduler import CollectorScheduler


@dataclass(slots=True)
class CollectorRuntimeEngine:
    """Coordinate the collector runtime lifecycle."""

    scheduler: CollectorScheduler
    dispatcher: CollectorDispatcher
    metrics: CollectorRuntimeMetrics = field(default_factory=CollectorRuntimeMetrics)
    lifecycle: CollectorRuntimeLifecycle = field(
        default_factory=CollectorRuntimeLifecycle
    )

    def __post_init__(self) -> None:
        """Synchronize runtime metrics across collaborators."""

        self.dispatcher.metrics = self.metrics
        self.dispatcher.executor.metrics = self.metrics

    async def start(self) -> None:
        """Start runtime services."""

        await self.lifecycle.start()

    async def stop(self) -> None:
        """Stop runtime services."""

        await self.lifecycle.stop()

    async def submit(
        self, context: CollectorRuntimeContext, *, priority: int = 0
    ) -> CollectorJob:
        """Schedule a new job."""

        self.metrics.record_submitted()
        return await self.scheduler.schedule(context, priority=priority)

    async def run_next(self) -> CollectorExecutionResult:
        """Execute the next queued job."""

        return await self.dispatcher.run_once()

    async def run_job(self, job: CollectorJob) -> CollectorExecutionResult:
        """Execute the next scheduled job."""

        return await self.dispatcher.dispatch(job)
