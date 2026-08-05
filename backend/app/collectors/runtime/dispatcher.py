"""Collector runtime dispatcher."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.collectors.execution.result import CollectorExecutionResult
from backend.app.collectors.runtime.executor import CollectorExecutor
from backend.app.collectors.runtime.job import CollectorJob
from backend.app.collectors.runtime.metrics import CollectorRuntimeMetrics
from backend.app.collectors.runtime.scheduler import CollectorScheduler


@dataclass(slots=True)
class CollectorDispatcher:
    """Dispatch scheduled jobs to the collector executor."""

    executor: CollectorExecutor
    scheduler: CollectorScheduler
    metrics: CollectorRuntimeMetrics

    async def dispatch(self, job: CollectorJob) -> CollectorExecutionResult:
        """Execute a single job and return its result."""

        return await self.executor.execute(job)

    async def run_once(self) -> CollectorExecutionResult:
        """Execute the next queued job."""

        job = await self.scheduler.next_job()
        return await self.dispatch(job)
