from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4


class ScheduleState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class ScheduleKind(StrEnum):
    DISCOVERY = "discovery"
    REPORTING = "reporting"


class ScheduleType(StrEnum):
    INTERVAL = "interval"
    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass(frozen=True, slots=True)
class Schedule:
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    kind: ScheduleKind = ScheduleKind.DISCOVERY
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    enabled: bool = True
    interval_seconds: int | None = None
    start_at: datetime | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: ScheduleState = ScheduleState.ACTIVE
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScheduleExecution:
    id: UUID = field(default_factory=uuid4)
    schedule_id: UUID = field(default_factory=uuid4)
    executed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "scheduled"
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class WorkerInfo:
    id: str
    kind: str
    status: str = "alive"
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkerMetrics:
    active_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    last_updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class WorkerHeartbeat:
    worker_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class WorkerLease:
    worker_id: str
    lease_id: UUID = field(default_factory=uuid4)
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(UTC) + timedelta(minutes=5)
    )


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    schedule_id: UUID
    executed: bool
    status: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class SchedulerStatistics:
    total_schedules: int
    enabled_schedules: int
    disabled_schedules: int
    active_workers: int
    stale_workers: int
