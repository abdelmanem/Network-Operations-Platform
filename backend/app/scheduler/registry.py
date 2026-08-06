from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from backend.app.scheduler.models import (
    WorkerHeartbeat,
    WorkerInfo,
    WorkerLease,
    WorkerMetrics,
)


class WorkerStatus(StrEnum):
    ALIVE = "alive"
    STALE = "stale"
    STOPPING = "stopping"


@dataclass(slots=True)
class WorkerRegistry:
    heartbeat_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=2))
    _workers: dict[str, WorkerInfo] = field(default_factory=dict, init=False)
    _metrics: dict[str, WorkerMetrics] = field(default_factory=dict, init=False)

    async def register_worker(self, worker_id: str, kind: str) -> WorkerInfo:
        worker = WorkerInfo(id=worker_id, kind=kind)
        self._workers[worker_id] = worker
        self._metrics[worker_id] = WorkerMetrics()
        return worker

    async def heartbeat(
        self, worker_id: str, *, now: datetime | None = None
    ) -> WorkerHeartbeat:
        timestamp = now or datetime.now(UTC)
        worker = self._workers.get(worker_id)
        if worker is None:
            worker = await self.register_worker(worker_id, "scheduler")
        updated = WorkerInfo(
            id=worker.id,
            kind=worker.kind,
            status=WorkerStatus.ALIVE.value,
            registered_at=worker.registered_at,
            last_heartbeat_at=timestamp,
            metadata=worker.metadata,
        )
        self._workers[worker_id] = updated
        return WorkerHeartbeat(worker_id=worker_id, timestamp=timestamp)

    async def lease(
        self, worker_id: str, *, expires_at: datetime | None = None
    ) -> WorkerLease:
        lease = WorkerLease(
            worker_id=worker_id,
            expires_at=expires_at or datetime.now(UTC) + timedelta(minutes=5),
        )
        return lease

    def detect_stale_workers(
        self, *, now: datetime | None = None
    ) -> tuple[WorkerInfo, ...]:
        current = now or datetime.now(UTC)
        stale: list[WorkerInfo] = []
        for worker in self._workers.values():
            if current - worker.last_heartbeat_at > self.heartbeat_ttl:
                stale.append(worker)
        return tuple(stale)

    def list_workers(self) -> tuple[WorkerInfo, ...]:
        return tuple(self._workers.values())

    def get_metrics(self, worker_id: str) -> WorkerMetrics | None:
        return self._metrics.get(worker_id)
