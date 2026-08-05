"""Collector runtime scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.job import CollectorJob, CollectorJobQueue


@dataclass(slots=True)
class CollectorScheduler:
    """Schedule collector jobs."""

    queue: CollectorJobQueue = field(default_factory=CollectorJobQueue)

    async def schedule(
        self, context: CollectorRuntimeContext, *, priority: int = 0
    ) -> CollectorJob:
        """Create and enqueue a job."""

        job = CollectorJob(context=context, priority=priority)
        job.state.mark_queued()
        await self.queue.put(job)
        return job

    async def submit(self, job: CollectorJob) -> CollectorJob:
        """Enqueue an existing job."""

        job.state.mark_queued()
        await self.queue.put(job)
        return job

    async def next_job(self) -> CollectorJob:
        """Return the next queued job."""

        return await self.queue.get()
