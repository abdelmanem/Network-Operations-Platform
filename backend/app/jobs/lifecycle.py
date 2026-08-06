"""Job lifecycle and graceful shutdown support."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass(slots=True)
class JobLifecycleManager:
    """Manage worker lifecycle and graceful shutdown."""

    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    worker_tasks: list[asyncio.Task[None]] = field(default_factory=list)

    def create_worker(self, coro: asyncio.Future[None] | asyncio.Task[None]) -> asyncio.Task[None]:
        """Create and track a worker task."""

        task = asyncio.create_task(coro)
        self.worker_tasks.append(task)
        return task

    async def shutdown(self) -> None:
        """Stop the workers and wait for completion."""

        self.stop_event.set()
        if not self.worker_tasks:
            return

        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
