from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.app.schemas.common import PaginatedResponse
from pydantic import BaseModel, Field


class DiscoveryJobRequest(BaseModel):
    """Request payload for triggering a discovery job."""

    collector_contexts: list[dict[str, object]] = Field(default_factory=list)
    policies: list[dict[str, object]] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)
    timeout_seconds: float | None = Field(default=None, ge=0.0)


class JobStatusResponse(BaseModel):
    """Status representation for a queued or completed job."""

    job_id: UUID
    status: str
    message: str | None = None
    created_at: datetime
    updated_at: datetime
    attempts: int
    progress: float | None = None


class JobSubmissionResponse(BaseModel):
    """Acknowledgement returned when a job is submitted."""

    job_id: UUID
    status: str = "queued"
    message: str = "Job accepted for processing."


class JobListResponse(PaginatedResponse[JobStatusResponse]):
    """Paginated list of jobs."""

    pass
