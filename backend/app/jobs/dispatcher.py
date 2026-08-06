"""Dispatch jobs for execution and publish lifecycle events."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from backend.app.events.interfaces import EventPublisher
from backend.app.jobs.metrics import JobMetrics
from backend.app.jobs.models import Job
from backend.app.jobs.notifications import (
    JobNotificationEventNames,
    publish_job_event,
)
from backend.app.jobs.progress import JobProgress
from backend.app.orchestration.engine import OrchestrationEngine
from backend.app.orchestration.results import OrchestrationResult
from backend.app.orchestration.state import OrchestrationStatus


@dataclass(slots=True)
class JobDispatcher:
    """Dispatch jobs to the orchestration engine."""

    engine: OrchestrationEngine
    max_concurrent_jobs: int = 4
    event_publisher: EventPublisher | None = None
    metrics: JobMetrics = field(default_factory=JobMetrics)
    _semaphore: asyncio.Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.max_concurrent_jobs)

    async def dispatch(self, job: Job) -> OrchestrationResult:
        """Run one job through the orchestration engine."""

        if job.cancellation_token.is_cancelled:
            job.state.mark_cancelled(job.cancellation_token.reason or "Job cancelled.")
            self.metrics.record_cancelled()
            await publish_job_event(
                self.event_publisher,
                JobNotificationEventNames().JOB_CANCELLED,
                job,
                reason=job.cancellation_token.reason,
            )
            raise asyncio.CancelledError(job.cancellation_token.reason)

        async with self._semaphore:
            self.metrics.record_started()
            job.state.increment_attempts()
            job.state.mark_running()
            await publish_job_event(
                self.event_publisher,
                JobNotificationEventNames().JOB_STARTED,
                job,
            )
            try:
                if job.request.timeout_seconds is not None:
                    result = await asyncio.wait_for(
                        self.engine.run(
                            job.request.context, priority=job.request.priority
                        ),
                        timeout=job.request.timeout_seconds,
                    )
                else:
                    result = await self.engine.run(
                        job.request.context, priority=job.request.priority
                    )
            except TimeoutError as exc:
                job.state.mark_timed_out(str(exc))
                self.metrics.record_timed_out()
                await publish_job_event(
                    self.event_publisher,
                    JobNotificationEventNames().JOB_TIMED_OUT,
                    job,
                    error=str(exc),
                )
                raise
            except asyncio.CancelledError:
                job.state.mark_cancelled(
                    job.cancellation_token.reason or "Job cancelled."
                )
                self.metrics.record_cancelled()
                await publish_job_event(
                    self.event_publisher,
                    JobNotificationEventNames().JOB_CANCELLED,
                    job,
                    reason=job.cancellation_token.reason,
                )
                raise
            except Exception as exc:
                job.state.mark_failed(str(exc))
                self.metrics.record_failed()
                await publish_job_event(
                    self.event_publisher,
                    JobNotificationEventNames().JOB_FAILED,
                    job,
                    error=str(exc),
                )
                raise
            else:
                if result.status == OrchestrationStatus.CANCELLED:
                    job.state.mark_cancelled(result.error_message)
                    self.metrics.record_cancelled()
                    await publish_job_event(
                        self.event_publisher,
                        JobNotificationEventNames().JOB_CANCELLED,
                        job,
                        reason=result.error_message,
                    )
                elif result.status == OrchestrationStatus.FAILED:
                    job.state.mark_failed(result.error_message or "Job failed.")
                    self.metrics.record_failed()
                    await publish_job_event(
                        self.event_publisher,
                        JobNotificationEventNames().JOB_FAILED,
                        job,
                        error=result.error_message,
                    )
                else:
                    job.state.mark_completed("Job completed successfully.")
                    self.metrics.record_completed()
                    await publish_job_event(
                        self.event_publisher,
                        JobNotificationEventNames().JOB_COMPLETED,
                        job,
                    )
                return result

    async def report_progress(self, job: Job, progress: JobProgress) -> None:
        """Publish progress for a running job."""

        if job.progress_callback is not None:
            result = job.progress_callback(progress)
            if result is not None:
                await result

        await publish_job_event(
            self.event_publisher,
            JobNotificationEventNames().JOB_PROGRESS,
            job,
            step=progress.step,
            completed_steps=progress.completed_steps,
            total_steps=progress.total_steps,
            percent=progress.percent,
            message=progress.message,
        )
