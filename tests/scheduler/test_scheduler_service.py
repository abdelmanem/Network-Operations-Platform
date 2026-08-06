from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from backend.app.core.application import create_application
from backend.app.scheduler.models import (
    Schedule,
)
from backend.app.scheduler.registry import WorkerRegistry, WorkerStatus
from backend.app.scheduler.repository import InMemorySchedulerRepository
from backend.app.scheduler.service import SchedulerService
from backend.app.schemas.scheduler import (
    ScheduleCreateRequest,
    ScheduleUpdateRequest,
)
from fastapi.testclient import TestClient


class FakeJobManager:
    def __init__(self) -> None:
        self.submissions: list[dict[str, object]] = []

    async def submit_job(self, request: object) -> object:
        self.submissions.append({"request": request})
        return type("Submission", (), {"job": type("Job", (), {"id": uuid4()})()})()


@pytest.mark.anyio
async def test_register_and_dispatch_interval_schedule() -> None:
    repository = InMemorySchedulerRepository()
    job_manager = FakeJobManager()
    registry = WorkerRegistry()
    service = SchedulerService(
        repository=repository,
        job_manager=job_manager,
        worker_registry=registry,
    )

    created = await service.register_schedule(
        ScheduleCreateRequest(
            name="discovery",
            kind="discovery",
            schedule_type="interval",
            interval_seconds=60,
            enabled=True,
        )
    )

    assert isinstance(created, Schedule)
    assert created.next_run_at is not None

    results = await service.dispatch_due_jobs(
        now=created.next_run_at + timedelta(seconds=1)
    )
    assert len(results) == 1
    assert len(job_manager.submissions) == 1


@pytest.mark.anyio
async def test_update_pause_resume_and_delete_schedule() -> None:
    repository = InMemorySchedulerRepository()
    service = SchedulerService(repository=repository, job_manager=None)
    created = await service.register_schedule(
        ScheduleCreateRequest(
            name="reporting",
            kind="reporting",
            schedule_type="daily",
            enabled=True,
        )
    )

    updated = await service.update_schedule(
        created.id,
        ScheduleUpdateRequest(name="reporting-updated", enabled=False),
    )
    assert updated.name == "reporting-updated"
    assert updated.enabled is False

    paused = await service.pause_schedule(created.id)
    assert paused.enabled is False

    resumed = await service.resume_schedule(created.id)
    assert resumed.enabled is True

    deleted = await service.delete_schedule(created.id)
    assert deleted is True
    assert await service.get_schedule(created.id) is None


@pytest.mark.anyio
async def test_worker_registration_heartbeat_and_stale_detection() -> None:
    registry = WorkerRegistry()
    worker = await registry.register_worker("worker-1", "scheduler")
    assert worker.status == WorkerStatus.ALIVE

    await registry.heartbeat("worker-1", now=datetime.now(UTC))
    stale = registry.detect_stale_workers(now=datetime.now(UTC) + timedelta(minutes=5))
    assert stale[0].id == "worker-1"


@pytest.mark.anyio
async def test_scheduler_statistics_include_counts() -> None:
    repository = InMemorySchedulerRepository()
    service = SchedulerService(repository=repository, job_manager=None)
    await service.register_schedule(
        ScheduleCreateRequest(
            name="one",
            kind="discovery",
            schedule_type="interval",
            interval_seconds=60,
            enabled=True,
        )
    )
    await service.register_schedule(
        ScheduleCreateRequest(
            name="two",
            kind="reporting",
            schedule_type="weekly",
            enabled=False,
        )
    )

    stats = await service.get_statistics()
    assert stats.total_schedules == 2
    assert stats.enabled_schedules == 1
    assert stats.disabled_schedules == 1


def test_scheduler_api_endpoints() -> None:
    app = create_application()
    client = TestClient(app)

    response = client.get("/api/v1/scheduler/schedules")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["items"], list)

    response = client.get("/api/v1/scheduler/statistics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_schedules"] >= 0
