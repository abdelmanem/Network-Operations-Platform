from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session, get_job_manager
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.discovery.context import DiscoveryTarget
from backend.app.jobs.manager import JobManager
from backend.app.jobs.models import JobRequest
from backend.app.orchestration.context import CancellationToken, OrchestrationContext
from backend.app.schemas.jobs import (
    DiscoveryJobRequest,
    JobListResponse,
    JobStatusResponse,
    JobSubmissionResponse,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "/discovery",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobSubmissionResponse,
    summary="Submit a discovery job",
)
async def submit_discovery_job(
    payload: DiscoveryJobRequest,
    request: Request,
    manager: Annotated[JobManager, Depends(get_job_manager)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> JobSubmissionResponse:
    context = OrchestrationContext(
        collector_contexts=tuple(
            _collector_context_from_payload(item) for item in payload.collector_contexts
        ),
        policies=tuple(),
        metadata=dict(payload.metadata),
        cancellation_token=CancellationToken(),
        progress_callback=None,
    )
    job_request = JobRequest(
        context=context,
        priority=payload.priority,
        timeout_seconds=payload.timeout_seconds,
    )
    result = await manager.submit_job(job_request)
    return JobSubmissionResponse(job_id=result.job.id, status="queued")


@router.get("/{job_id}", response_model=JobStatusResponse, summary="Get a job status")
async def get_job_status(
    job_id: UUID,
    manager: Annotated[JobManager, Depends(get_job_manager)],
) -> JobStatusResponse:
    job = await manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return JobStatusResponse(
        job_id=job.id,
        status=job.state.status.value,
        message=job.state.message,
        created_at=job.created_at,
        updated_at=job.state.updated_at,
        attempts=job.state.attempts,
        progress=_progress(job),
    )


@router.delete("/{job_id}", summary="Cancel a job")
async def cancel_job(
    job_id: UUID,
    manager: Annotated[JobManager, Depends(get_job_manager)],
) -> dict[str, str]:
    await manager.cancel_job(str(job_id), reason="Cancelled through API")
    return {"status": "cancelled", "job_id": str(job_id)}


@router.get("", response_model=JobListResponse, summary="List jobs")
async def list_jobs(
    manager: Annotated[JobManager, Depends(get_job_manager)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> JobListResponse:
    jobs = await manager.list_jobs()
    ordered = sorted(jobs, key=lambda item: item.created_at, reverse=True)
    start = (page - 1) * page_size
    end = start + page_size
    items = [
        JobStatusResponse(
            job_id=job.id,
            status=job.state.status.value,
            message=job.state.message,
            created_at=job.created_at,
            updated_at=job.state.updated_at,
            attempts=job.state.attempts,
            progress=_progress(job),
        )
        for job in ordered[start:end]
    ]
    return JobListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=len(ordered),
        has_next=end < len(ordered),
    )


def _collector_context_from_payload(
    payload: dict[str, object],
) -> CollectorRuntimeContext:
    target_payload = payload.get("target")
    if isinstance(target_payload, dict):
        target = DiscoveryTarget(
            identifier=str(target_payload.get("identifier", "")),
            address=str(target_payload.get("address", "")),
            metadata={
                k: v
                for k, v in target_payload.items()
                if k not in {"identifier", "address"}
            },
        )
    else:
        target = DiscoveryTarget(identifier="", address="")
    return CollectorRuntimeContext(target=target)


def _progress(job: object) -> float | None:
    if not hasattr(job, "history") or not job.history:
        return None
    latest = job.history[-1]
    state = latest.state
    if state.status == "completed":
        return 100.0
    return None
