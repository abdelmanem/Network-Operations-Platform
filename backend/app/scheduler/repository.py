from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.scheduler.infrastructure.models import (
    ScheduleExecutionRecord,
    ScheduleRecord,
)
from backend.app.scheduler.models import (
    Schedule,
    ScheduleExecution,
    ScheduleKind,
    ScheduleState,
    ScheduleType,
)


class SchedulerRepository(ABC):
    @abstractmethod
    async def save_schedule(self, schedule: Schedule) -> Schedule:
        raise NotImplementedError

    @abstractmethod
    async def get_schedule(self, schedule_id: UUID) -> Schedule | None:
        raise NotImplementedError

    @abstractmethod
    async def list_schedules(self) -> tuple[Schedule, ...]:
        raise NotImplementedError

    @abstractmethod
    async def delete_schedule(self, schedule_id: UUID) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def append_execution(self, execution: ScheduleExecution) -> ScheduleExecution:
        raise NotImplementedError

    @abstractmethod
    async def list_executions(self, schedule_id: UUID) -> tuple[ScheduleExecution, ...]:
        raise NotImplementedError


class InMemorySchedulerRepository(SchedulerRepository):
    def __init__(self) -> None:
        self._schedules: dict[UUID, Schedule] = {}
        self._executions: list[ScheduleExecution] = []

    async def save_schedule(self, schedule: Schedule) -> Schedule:
        self._schedules[schedule.id] = schedule
        return schedule

    async def get_schedule(self, schedule_id: UUID) -> Schedule | None:
        return self._schedules.get(schedule_id)

    async def list_schedules(self) -> tuple[Schedule, ...]:
        return tuple(self._schedules.values())

    async def delete_schedule(self, schedule_id: UUID) -> bool:
        return self._schedules.pop(schedule_id, None) is not None

    async def append_execution(self, execution: ScheduleExecution) -> ScheduleExecution:
        self._executions.append(execution)
        return execution

    async def list_executions(self, schedule_id: UUID) -> tuple[ScheduleExecution, ...]:
        return tuple(
            item for item in self._executions if item.schedule_id == schedule_id
        )


class SQLAlchemySchedulerRepository(SchedulerRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def save_schedule(self, schedule: Schedule) -> Schedule:
        row = self._session.get(ScheduleRecord, schedule.id)
        if row is None:
            row = ScheduleRecord(
                id=schedule.id,
                name=schedule.name,
                kind=schedule.kind.value,
                schedule_type=schedule.schedule_type.value,
                enabled=schedule.enabled,
                interval_seconds=schedule.interval_seconds,
                start_at=schedule.start_at,
                next_run_at=schedule.next_run_at,
                last_run_at=schedule.last_run_at,
                created_at=schedule.created_at,
                updated_at=schedule.updated_at,
                state=schedule.state.value,
                metadata_json=schedule.metadata,
            )
            self._session.add(row)
        else:
            row.name = schedule.name
            row.kind = schedule.kind.value
            row.schedule_type = schedule.schedule_type.value
            row.enabled = schedule.enabled
            row.interval_seconds = schedule.interval_seconds
            row.start_at = schedule.start_at
            row.next_run_at = schedule.next_run_at
            row.last_run_at = schedule.last_run_at
            row.updated_at = schedule.updated_at
            row.state = schedule.state.value
            row.metadata_json = schedule.metadata
        self._session.commit()
        self._session.refresh(row)
        return self._to_schedule(row)

    async def get_schedule(self, schedule_id: UUID) -> Schedule | None:
        row = self._session.get(ScheduleRecord, schedule_id)
        return self._to_schedule(row) if row is not None else None

    async def list_schedules(self) -> tuple[Schedule, ...]:
        statement = select(ScheduleRecord)
        rows = self._session.scalars(statement).all()
        return tuple(self._to_schedule(row) for row in rows)

    async def delete_schedule(self, schedule_id: UUID) -> bool:
        row = self._session.get(ScheduleRecord, schedule_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.commit()
        return True

    async def append_execution(self, execution: ScheduleExecution) -> ScheduleExecution:
        row = ScheduleExecutionRecord(
            id=execution.id,
            schedule_id=execution.schedule_id,
            executed_at=execution.executed_at,
            status=execution.status,
            detail=execution.detail,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_execution(row)

    async def list_executions(self, schedule_id: UUID) -> tuple[ScheduleExecution, ...]:
        statement = select(ScheduleExecutionRecord).where(
            ScheduleExecutionRecord.schedule_id == schedule_id
        )
        rows = self._session.scalars(statement).all()
        return tuple(self._to_execution(row) for row in rows)

    def _to_schedule(self, row: ScheduleRecord | None) -> Schedule | None:
        if row is None:
            return None
        return Schedule(
            id=row.id,
            name=row.name,
            kind=ScheduleKind(row.kind),
            schedule_type=ScheduleType(row.schedule_type),
            enabled=row.enabled,
            interval_seconds=row.interval_seconds,
            start_at=row.start_at,
            next_run_at=row.next_run_at,
            last_run_at=row.last_run_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
            state=ScheduleState(row.state),
            metadata=dict(row.metadata_json or {}),
        )

    def _to_execution(self, row: ScheduleExecutionRecord) -> ScheduleExecution:
        return ScheduleExecution(
            id=row.id,
            schedule_id=row.schedule_id,
            executed_at=row.executed_at,
            status=row.status,
            detail=row.detail,
        )
