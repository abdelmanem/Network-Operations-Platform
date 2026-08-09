"""Internal event definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class BaseEvent:
    """Base contract for internal application events."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class JobSubmittedEvent(BaseEvent):
    """Raised when a job is submitted for execution."""

    def __init__(
        self,
        *,
        job_id: str,
        status: str,
        payload: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        super().__init__(
            name="job.submitted",
            payload={"job_id": job_id, "status": status, **(payload or {})},
            occurred_at=occurred_at or datetime.now(UTC),
        )
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "status", status)


class JobCompletedEvent(BaseEvent):
    """Raised when a job completes successfully."""

    def __init__(
        self,
        *,
        job_id: str,
        status: str,
        payload: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        super().__init__(
            name="job.completed",
            payload={"job_id": job_id, "status": status, **(payload or {})},
            occurred_at=occurred_at or datetime.now(UTC),
        )
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "status", status)


class JobFailedEvent(BaseEvent):
    """Raised when a job fails."""

    def __init__(
        self,
        *,
        job_id: str,
        status: str,
        payload: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        super().__init__(
            name="job.failed",
            payload={"job_id": job_id, "status": status, **(payload or {})},
            occurred_at=occurred_at or datetime.now(UTC),
        )
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "status", status)
