"""Repository abstractions for job persistence and history."""

from __future__ import annotations

from uuid import UUID

from backend.app.jobs.models import Job, JobHistoryRecord


class JobRepository:
    """Repository interface for job persistence."""

    async def save(self, job: Job) -> None:
        """Persist the current job state."""

        raise NotImplementedError

    async def get(self, job_id: UUID) -> Job | None:
        """Return a persisted job by identifier."""

        raise NotImplementedError

    async def list_jobs(self) -> tuple[Job, ...]:
        """Return all persisted jobs."""

        raise NotImplementedError

    async def append_history(self, job_id: UUID, record: JobHistoryRecord) -> None:
        """Append an immutable history record for a job."""

        raise NotImplementedError


class InMemoryJobRepository(JobRepository):
    """In-memory repository for job persistence and history."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, Job] = {}
        self._history: dict[UUID, list[JobHistoryRecord]] = {}

    async def save(self, job: Job) -> None:
        self._jobs[job.id] = job
        self._history.setdefault(job.id, []).extend(job.history)

    async def get(self, job_id: UUID) -> Job | None:
        return self._jobs.get(job_id)

    async def list_jobs(self) -> tuple[Job, ...]:
        return tuple(self._jobs.values())

    async def append_history(self, job_id: UUID, record: JobHistoryRecord) -> None:
        self._history.setdefault(job_id, []).append(record)
