"""Orchestration event helpers."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.events.models import BaseEvent
from backend.app.orchestration.jobs import OrchestrationJob
from backend.app.orchestration.progress import OrchestrationProgress


@dataclass(frozen=True, slots=True)
class OrchestrationEventNames:
    """Event names emitted by orchestration."""

    RUN_STARTED: str = "orchestration.run.started"
    RUN_PROGRESS: str = "orchestration.run.progress"
    RUN_SUCCEEDED: str = "orchestration.run.succeeded"
    RUN_FAILED: str = "orchestration.run.failed"
    RUN_CANCELLED: str = "orchestration.run.cancelled"


def run_event(name: str, job: OrchestrationJob, **payload: object) -> BaseEvent:
    """Create an orchestration event."""

    return BaseEvent(
        name=name,
        payload={
            "job_id": str(job.id),
            "run_id": str(job.context.run_id),
            **payload,
        },
    )


def progress_payload(progress: OrchestrationProgress) -> dict[str, object]:
    """Return serializable progress payload."""

    return {
        "step": progress.step,
        "completed_steps": progress.completed_steps,
        "total_steps": progress.total_steps,
        "percent": progress.percent,
        "message": progress.message,
    }
