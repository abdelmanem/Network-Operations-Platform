from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from backend.app.jobs.models import JobRequest, JobSubmissionResult
from backend.app.orchestration.context import CancellationToken, OrchestrationContext
from backend.app.scheduler.models import (
    ExecutionResult,
    Schedule,
    ScheduleExecution,
    ScheduleKind,
    SchedulerStatistics,
    ScheduleState,
    ScheduleType,
)
from backend.app.scheduler.registry import WorkerRegistry
from backend.app.scheduler.repository import SchedulerRepository
from backend.app.schemas.scheduler import (
    ScheduleCreateRequest,
    ScheduleUpdateRequest,
)


class _JobManagerProtocol(Protocol):
    async def submit_job(self, request: JobRequest) -> JobSubmissionResult: ...


class SchedulerService:
    def __init__(
        self,
        *,
        repository: SchedulerRepository,
        job_manager: _JobManagerProtocol | None = None,
        worker_registry: WorkerRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.job_manager = job_manager
        self.worker_registry = worker_registry or WorkerRegistry()

    async def register_schedule(self, payload: ScheduleCreateRequest) -> Schedule:
        now = datetime.now(UTC)
        schedule = Schedule(
            name=payload.name,
            kind=ScheduleKind(payload.kind),
            schedule_type=ScheduleType(payload.schedule_type),
            enabled=payload.enabled,
            interval_seconds=payload.interval_seconds,
            start_at=payload.start_at or now,
            next_run_at=self._compute_next_run(
                payload, start_at=payload.start_at or now
            ),
            last_run_at=None,
            state=ScheduleState.ACTIVE if payload.enabled else ScheduleState.DISABLED,
            metadata=dict(payload.metadata or {}),
        )
        return await self.repository.save_schedule(schedule)

    async def update_schedule(
        self, schedule_id: UUID, payload: ScheduleUpdateRequest
    ) -> Schedule:
        existing = await self.repository.get_schedule(schedule_id)
        if existing is None:
            raise KeyError(schedule_id)
        updated = Schedule(
            id=existing.id,
            name=payload.name or existing.name,
            kind=existing.kind,
            schedule_type=existing.schedule_type,
            enabled=(
                payload.enabled if payload.enabled is not None else existing.enabled
            ),
            interval_seconds=existing.interval_seconds,
            start_at=existing.start_at,
            next_run_at=existing.next_run_at,
            last_run_at=existing.last_run_at,
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
            state=(
                ScheduleState.ACTIVE
                if payload.enabled is not False
                else ScheduleState.DISABLED
            ),
            metadata=existing.metadata,
        )
        return await self.repository.save_schedule(updated)

    async def delete_schedule(self, schedule_id: UUID) -> bool:
        return await self.repository.delete_schedule(schedule_id)

    async def get_schedule(self, schedule_id: UUID) -> Schedule | None:
        return await self.repository.get_schedule(schedule_id)

    async def list_schedules(self) -> tuple[Schedule, ...]:
        return await self.repository.list_schedules()

    async def pause_schedule(self, schedule_id: UUID) -> Schedule:
        existing = await self.repository.get_schedule(schedule_id)
        if existing is None:
            raise KeyError(schedule_id)
        updated = Schedule(
            id=existing.id,
            name=existing.name,
            kind=existing.kind,
            schedule_type=existing.schedule_type,
            enabled=False,
            interval_seconds=existing.interval_seconds,
            start_at=existing.start_at,
            next_run_at=existing.next_run_at,
            last_run_at=existing.last_run_at,
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
            state=ScheduleState.PAUSED,
            metadata=existing.metadata,
        )
        return await self.repository.save_schedule(updated)

    async def resume_schedule(self, schedule_id: UUID) -> Schedule:
        existing = await self.repository.get_schedule(schedule_id)
        if existing is None:
            raise KeyError(schedule_id)
        updated = Schedule(
            id=existing.id,
            name=existing.name,
            kind=existing.kind,
            schedule_type=existing.schedule_type,
            enabled=True,
            interval_seconds=existing.interval_seconds,
            start_at=existing.start_at,
            next_run_at=self._compute_next_run_from_existing(existing),
            last_run_at=existing.last_run_at,
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
            state=ScheduleState.ACTIVE,
            metadata=existing.metadata,
        )
        return await self.repository.save_schedule(updated)

    async def dispatch_due_jobs(
        self, *, now: datetime | None = None
    ) -> tuple[ExecutionResult, ...]:
        current = now or datetime.now(UTC)
        schedules = await self.repository.list_schedules()
        results: list[ExecutionResult] = []
        for schedule in schedules:
            if not schedule.enabled or schedule.next_run_at is None:
                continue
            if schedule.next_run_at <= current:
                if self.job_manager is not None:
                    request = JobRequest(
                        context=OrchestrationContext(
                            collector_contexts=(),
                            policies=(),
                            exceptions=(),
                            metadata=schedule.metadata,
                            cancellation_token=CancellationToken(),
                            progress_callback=None,
                        ),
                        priority=0,
                    )
                    await self.job_manager.submit_job(request)
                await self.repository.append_execution(
                    ScheduleExecution(
                        schedule_id=schedule.id,
                        executed_at=current,
                        status="dispatched",
                        detail=schedule.kind.value,
                    )
                )
                updated = Schedule(
                    id=schedule.id,
                    name=schedule.name,
                    kind=schedule.kind,
                    schedule_type=schedule.schedule_type,
                    enabled=schedule.enabled,
                    interval_seconds=schedule.interval_seconds,
                    start_at=schedule.start_at,
                    next_run_at=self._compute_next_run_from_existing(
                        schedule, now=current
                    ),
                    last_run_at=current,
                    created_at=schedule.created_at,
                    updated_at=current,
                    state=schedule.state,
                    metadata=schedule.metadata,
                )
                await self.repository.save_schedule(updated)
                results.append(
                    ExecutionResult(
                        schedule_id=schedule.id,
                        executed=True,
                        status="dispatched",
                        detail=schedule.kind.value,
                    )
                )
        return tuple(results)

    async def get_statistics(self) -> SchedulerStatistics:
        schedules = await self.repository.list_schedules()
        workers = (
            self.worker_registry.list_workers()
            if self.worker_registry is not None
            else ()
        )
        return SchedulerStatistics(
            total_schedules=len(schedules),
            enabled_schedules=sum(1 for item in schedules if item.enabled),
            disabled_schedules=sum(1 for item in schedules if not item.enabled),
            active_workers=len(workers),
            stale_workers=len(self.worker_registry.detect_stale_workers()),
        )

    def _compute_next_run(
        self, payload: ScheduleCreateRequest, *, start_at: datetime
    ) -> datetime:
        if payload.schedule_type == "one_time":
            return payload.start_at or start_at
        if payload.schedule_type == "daily":
            return (payload.start_at or start_at) + timedelta(days=1)
        if payload.schedule_type == "weekly":
            return (payload.start_at or start_at) + timedelta(weeks=1)
        if payload.schedule_type == "monthly":
            return (payload.start_at or start_at) + timedelta(days=30)
        interval_seconds = payload.interval_seconds or 60
        return start_at + timedelta(seconds=interval_seconds)

    def _compute_next_run_from_existing(
        self, schedule: Schedule, *, now: datetime | None = None
    ) -> datetime:
        current = now or datetime.now(UTC)
        if schedule.schedule_type == ScheduleType.ONE_TIME:
            return schedule.next_run_at or current
        if schedule.schedule_type == ScheduleType.DAILY:
            return current + timedelta(days=1)
        if schedule.schedule_type == ScheduleType.WEEKLY:
            return current + timedelta(weeks=1)
        if schedule.schedule_type == ScheduleType.MONTHLY:
            return current + timedelta(days=30)
        interval_seconds = schedule.interval_seconds or 60
        return current + timedelta(seconds=interval_seconds)
