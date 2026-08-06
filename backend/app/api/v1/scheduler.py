from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import (
    get_application_container,
    get_db_session,
    get_job_manager,
)
from backend.app.jobs.manager import JobManager
from backend.app.scheduler.models import Schedule
from backend.app.scheduler.repository import SQLAlchemySchedulerRepository
from backend.app.scheduler.service import SchedulerService
from backend.app.schemas.scheduler import (
    ScheduleCreateRequest,
    ScheduleResponse,
    ScheduleUpdateRequest,
)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def get_scheduler_service(
    request: Request,
    db_session: Annotated[Session, Depends(get_db_session)],
    job_manager: Annotated[JobManager, Depends(get_job_manager)],
) -> SchedulerService:
    container = get_application_container(request)
    repository = SQLAlchemySchedulerRepository(db_session)
    return SchedulerService(
        repository=repository,
        job_manager=job_manager,
        worker_registry=container.worker_registry,
    )


@router.get("/schedules", response_model=dict[str, object])
async def list_schedules(
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
) -> dict[str, object]:
    schedules = await service.list_schedules()
    items = [_serialize_schedule(item) for item in schedules]
    return {"items": items}


@router.post(
    "/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED
)
async def create_schedule(
    payload: ScheduleCreateRequest,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
) -> ScheduleResponse:
    schedule = await service.register_schedule(payload)
    return _serialize_schedule(schedule)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    payload: ScheduleUpdateRequest,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
) -> ScheduleResponse:
    try:
        schedule = await service.update_schedule(schedule_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        ) from exc
    return _serialize_schedule(schedule)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
) -> None:
    deleted = await service.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )


@router.post("/schedules/{schedule_id}/pause", response_model=ScheduleResponse)
async def pause_schedule(
    schedule_id: UUID,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
) -> ScheduleResponse:
    try:
        schedule = await service.pause_schedule(schedule_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        ) from exc
    return _serialize_schedule(schedule)


@router.post("/schedules/{schedule_id}/resume", response_model=ScheduleResponse)
async def resume_schedule(
    schedule_id: UUID,
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
) -> ScheduleResponse:
    try:
        schedule = await service.resume_schedule(schedule_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        ) from exc
    return _serialize_schedule(schedule)


@router.get("/workers", response_model=dict[str, object])
async def list_workers(
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
) -> dict[str, object]:
    workers = service.worker_registry.list_workers()
    return {
        "items": [
            {
                "id": worker.id,
                "kind": worker.kind,
                "status": worker.status,
                "registered_at": worker.registered_at,
                "last_heartbeat_at": worker.last_heartbeat_at,
            }
            for worker in workers
        ]
    }


@router.get("/statistics", response_model=dict[str, object])
async def statistics(
    service: Annotated[SchedulerService, Depends(get_scheduler_service)],
) -> dict[str, object]:
    stats = await service.get_statistics()
    return {
        "total_schedules": stats.total_schedules,
        "enabled_schedules": stats.enabled_schedules,
        "disabled_schedules": stats.disabled_schedules,
        "active_workers": stats.active_workers,
        "stale_workers": stats.stale_workers,
    }


def _serialize_schedule(schedule: Schedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=str(schedule.id),
        name=schedule.name,
        kind=schedule.kind.value,
        schedule_type=schedule.schedule_type.value,
        enabled=schedule.enabled,
        interval_seconds=schedule.interval_seconds,
        next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at,
        state=schedule.state.value,
    )
