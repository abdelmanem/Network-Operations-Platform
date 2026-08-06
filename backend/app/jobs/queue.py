"""Priority queue for job execution."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import count

from backend.app.jobs.models import Job


@dataclass(slots=True)
class JobQueue:
    """Queue for scheduling jobs with priority."""

    _queue: asyncio.PriorityQueue[tuple[int, int, Job]] = field(
        default_factory=asyncio.PriorityQueue
    )
    _sequence: Iterator[int] = field(default_factory=count, init=False, repr=False)

    async def put(self, job: Job) -> None:
        """Add a job to the queue."""

        job.state.mark_queued()
        await self._queue.put((job.request.priority, next(self._sequence), job))

    async def get(self) -> Job:
        """Remove the next job from the queue."""

        _, _, job = await self._queue.get()
        return job

    def empty(self) -> bool:
        """Return whether the queue is empty."""

        return self._queue.empty()

    def qsize(self) -> int:
        """Return the current queue size."""

        return self._queue.qsize()
