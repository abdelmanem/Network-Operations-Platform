"""Collector runtime jobs and queue."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count
from uuid import UUID, uuid4

from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.state import CollectorExecutionState


@dataclass(slots=True)
class CollectorJob:
    """Represent a scheduled collector execution."""

    context: CollectorRuntimeContext
    priority: int = 0
    id: UUID = field(default_factory=uuid4)
    state: CollectorExecutionState = field(default_factory=CollectorExecutionState)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    cancellation_event: asyncio.Event = field(default_factory=asyncio.Event)

    def cancel(self, reason: str | None = None) -> None:
        """Request cancellation for the job."""

        self.cancellation_event.set()
        self.state.mark_cancelled(reason)

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation was requested."""

        return self.cancellation_event.is_set()


@dataclass(slots=True)
class CollectorJobQueue:
    """Priority queue for collector jobs."""

    _queue: asyncio.PriorityQueue[tuple[int, int, CollectorJob]] = field(
        default_factory=asyncio.PriorityQueue
    )
    _sequence: Iterator[int] = field(default_factory=count, init=False, repr=False)

    async def put(self, job: CollectorJob) -> None:
        """Add a job to the queue."""

        await self._queue.put((job.priority, next(self._sequence), job))

    async def get(self) -> CollectorJob:
        """Remove the next job from the queue."""

        _, _, job = await self._queue.get()
        return job

    def empty(self) -> bool:
        """Return whether the queue is empty."""

        return self._queue.empty()

    def qsize(self) -> int:
        """Return the current queue size."""

        return self._queue.qsize()
