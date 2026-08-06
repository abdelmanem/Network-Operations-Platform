"""Worker executing jobs from the queue."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from backend.app.jobs.dispatcher import JobDispatcher
from backend.app.jobs.lifecycle import JobLifecycleManager
from backend.app.jobs.notifications import JobNotificationEventNames, publish_job_event
from backend.app.jobs.queue import JobQueue
from backend.app.jobs.repository import JobRepository


@dataclass(slots=True)
class JobWorker:
    """Worker that consumes jobs from a queue and executes them."""

    queue: JobQueue
    dispatcher: JobDispatcher
    repository: JobRepository
    lifecycle: JobLifecycleManager
    polling_interval_seconds: float = 0.1
    _running: bool = field(default=False, init=False)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))

    async def run(self) -> None:
        """Run worker loop until shutdown is requested."""

        self._running = True
        while not self.lifecycle.stop_event.is_set():
            if self.queue.empty():
                await asyncio.sleep(self.polling_interval_seconds)
                continue

            job = await self.queue.get()
            await publish_job_event(
                self.dispatcher.event_publisher,
                JobNotificationEventNames().JOB_QUEUED,
                job,
            )
            await self.repository.save(job)
            try:
                await self.dispatcher.dispatch(job)
            except asyncio.CancelledError:
                self.logger.debug("Job worker cancelled job %s", job.id)
            except Exception as exc:  # pragma: no cover - defensive guard
                self.logger.exception("Job worker failed for %s: %s", job.id, exc)
            finally:
                await self.repository.save(job)
        self._running = False

    def start(self) -> asyncio.Task[None]:
        """Start the worker task."""

        return self.lifecycle.create_worker(self.run())
