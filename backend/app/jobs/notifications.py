"""Job event names and notification helpers."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.events.interfaces import EventPublisher
from backend.app.events.models import BaseEvent
from backend.app.jobs.models import Job


@dataclass(frozen=True, slots=True)
class JobNotificationEventNames:
    """Names of events emitted by the job framework."""

    JOB_SUBMITTED: str = "job.submitted"
    JOB_QUEUED: str = "job.queued"
    JOB_STARTED: str = "job.started"
    JOB_PROGRESS: str = "job.progress"
    JOB_COMPLETED: str = "job.completed"
    JOB_FAILED: str = "job.failed"
    JOB_CANCELLED: str = "job.cancelled"
    JOB_TIMED_OUT: str = "job.timed_out"
    JOB_RETRYING: str = "job.retrying"


def job_event(name: str, job: Job, **payload: object) -> BaseEvent:
    """Create a job framework event."""

    return BaseEvent(
        name=name,
        payload={
            "job_id": str(job.id),
            "status": job.state.status.value,
            "attempts": job.state.attempts,
            **payload,
        },
    )


async def publish_job_event(
    publisher: EventPublisher | None,
    name: str,
    job: Job,
    **payload: object,
) -> None:
    """Publish a job event if an event publisher exists."""

    if publisher is None:
        return

    await publisher.publish(job_event(name, job, **payload))
