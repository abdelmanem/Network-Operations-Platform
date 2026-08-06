"""Job manager that orchestrates submission, queueing, and lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from backend.app.orchestration.progress import OrchestrationProgress

from backend.app.events.interfaces import EventPublisher
from backend.app.jobs.dispatcher import JobDispatcher
from backend.app.jobs.lifecycle import JobLifecycleManager
from backend.app.jobs.metrics import JobMetrics
from backend.app.jobs.models import Job, JobRequest, JobSubmissionResult
from backend.app.jobs.notifications import (
    JobNotificationEventNames,
    publish_job_event,
)
from backend.app.jobs.progress import JobProgress
from backend.app.jobs.queue import JobQueue
from backend.app.jobs.repository import JobRepository
from backend.app.jobs.worker import JobWorker
from backend.app.orchestration.engine import OrchestrationEngine
from backend.app.orchestration.progress import OrchestrationProgress


@dataclass(slots=True)
class JobManager:
    """Manage jobs, queue, workers, and graceful shutdown."""

    engine: OrchestrationEngine
    repository: JobRepository
    event_publisher: EventPublisher | None = None
    max_concurrent_jobs: int = 4
    worker_count: int = 2
    polling_interval_seconds: float = 0.1
    lifecycle: JobLifecycleManager = field(default_factory=JobLifecycleManager)
    queue: JobQueue = field(default_factory=JobQueue)
    dispatcher: JobDispatcher = field(init=False)
    worker: JobWorker = field(init=False)
    metrics: JobMetrics = field(default_factory=JobMetrics)

    def __post_init__(self) -> None:
        self.dispatcher = JobDispatcher(
            engine=self.engine,
            max_concurrent_jobs=self.max_concurrent_jobs,
            event_publisher=self.event_publisher,
            metrics=self.metrics,
        )
        self.worker = JobWorker(
            queue=self.queue,
            dispatcher=self.dispatcher,
            repository=self.repository,
            lifecycle=self.lifecycle,
        )

    async def submit_job(self, request: JobRequest) -> JobSubmissionResult:
        """Submit a new job for execution."""

        original_callback = request.context.progress_callback
        event_publisher = self.event_publisher

        async def wrapped_progress(
            progress: OrchestrationProgress,
        ) -> None:
            if original_callback is not None:
                result = original_callback(progress)
                if result is not None:
                    await result

            if event_publisher is not None:
                await publish_job_event(
                    event_publisher,
                    JobNotificationEventNames().JOB_PROGRESS,
                    job,
                    step=progress.step,
                    completed_steps=progress.completed_steps,
                    total_steps=progress.total_steps,
                    percent=progress.percent,
                    message=progress.message,
                )

        wrapped_request = replace(
            request,
            context=replace(
                request.context,
                progress_callback=wrapped_progress,
                event_publisher=request.context.event_publisher or event_publisher,
            ),
        )

        async def emit_job_progress(progress: JobProgress) -> None:
            if event_publisher is not None:
                await publish_job_event(
                    event_publisher,
                    JobNotificationEventNames().JOB_PROGRESS,
                    job,
                    step=progress.step,
                    completed_steps=progress.completed_steps,
                    total_steps=progress.total_steps,
                    percent=progress.percent,
                    message=progress.message,
                )

        job = Job(
            request=wrapped_request,
            progress_callback=emit_job_progress,
            event_publisher=event_publisher,
            cancellation_token=wrapped_request.context.cancellation_token,
        )

        await self.repository.save(job)
        self.metrics.record_submitted()
        await publish_job_event(
            self.event_publisher,
            JobNotificationEventNames().JOB_SUBMITTED,
            job,
        )
        await self.queue.put(job)
        self.metrics.record_queued()
        return JobSubmissionResult(job=job, queued=True)

    async def start_workers(self) -> None:
        """Start worker tasks."""

        for _ in range(self.worker_count):
            self.worker.start()

    async def shutdown(self) -> None:
        """Stop workers gracefully."""

        await self.lifecycle.shutdown()

    async def cancel_job(self, job_id: str, reason: str = "Job cancelled.") -> None:
        """Request cancellation for a specific job."""

        job_uuid = UUID(job_id)
        job = await self.repository.get(job_uuid)
        if job is None:
            return
        job.cancel(reason)
        await self.repository.save(job)
        await publish_job_event(
            self.event_publisher,
            JobNotificationEventNames().JOB_CANCELLED,
            job,
            reason=reason,
        )

    async def get_job(self, job_id: UUID) -> Job | None:
        """Return a persisted job."""

        return await self.repository.get(job_id)

    async def list_jobs(self) -> tuple[Job, ...]:
        """Return all persisted jobs."""

        return await self.repository.list_jobs()
