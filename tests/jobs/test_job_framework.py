from __future__ import annotations

import asyncio

import pytest
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.comparison.engine import ComparisonEngine
from backend.app.compliance.domain.enums import RuleStatus
from backend.app.compliance.policies.models import Policy
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.discovery.context import DiscoveryTarget
from backend.app.evaluation.engine import EvaluationEngine
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import Device, DeviceType, Manufacturer
from backend.app.jobs import (
    CancellationToken as JobCancellationToken,
)
from backend.app.jobs import (
    InMemoryJobRepository,
    JobManager,
    JobNotificationEventNames,
    JobRequest,
    JobStatus,
)
from backend.app.models.base import BaseModel
from backend.app.orchestration import (
    CancellationToken,
    OrchestrationContext,
    OrchestrationEngine,
    OrchestrationStatus,
    WorkflowEngine,
)
from backend.app.orchestration.coordinator import DiscoveryCoordinator
from backend.app.persistence.unit_of_work import PersistenceUnitOfWork
from backend.app.snapshot.entities import (
    DeviceSnapshot,
)
from backend.app.snapshot.entities import (
    InventorySnapshot as LiveInventorySnapshot,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class FakeInventoryService:
    def __init__(
        self, snapshot: NetBoxInventorySnapshot, fail_once: bool = False
    ) -> None:
        self.snapshot = snapshot
        self.fail_once = fail_once
        self.calls = 0

    async def synchronize(
        self, *, force_refresh: bool = False
    ) -> NetBoxInventorySnapshot:
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise RuntimeError("temporary netbox failure")
        return self.snapshot


class FakeCollectorRuntime:
    def __init__(self, snapshot: LiveInventorySnapshot) -> None:
        self.snapshot = snapshot

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def submit(
        self, context: CollectorRuntimeContext, *, priority: int = 0
    ) -> object:
        return object()

    async def run_job(self, job: object) -> object:
        class FakeResult:
            snapshot = self.snapshot

        return FakeResult()

    async def collect(
        self, contexts: tuple[CollectorRuntimeContext, ...]
    ) -> tuple[LiveInventorySnapshot, tuple[object, ...]]:
        return self.snapshot, ()


class EventRecorder:
    def __init__(self) -> None:
        self.names: list[str] = []

    async def publish(self, event: object) -> None:
        self.names.append(event.name)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    BaseModel.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    with session_factory() as db_session:
        yield db_session


def _netbox_snapshot() -> NetBoxInventorySnapshot:
    manufacturer = Manufacturer(name="Cisco", slug="cisco")
    device_type = DeviceType(
        manufacturer=manufacturer,
        model="WS-C2960X",
        slug="ws-c2960x",
    )
    return NetBoxInventorySnapshot(
        devices=(
            Device(
                name="switch-01",
                device_type=device_type,
                serial="ABC123",
            ),
        )
    )


def _live_snapshot() -> LiveInventorySnapshot:
    return LiveInventorySnapshot(
        devices=(
            DeviceSnapshot(
                device_id="switch-01",
                name="switch-01",
                model="WS-C2960X",
                serial_number="XYZ999",
            ),
        )
    )


def _policy() -> Policy:
    rule = Rule.create(
        "serial-match",
        "Serial must match",
        RuleMetadata(version="1.0", status=RuleStatus.ACTIVE),
        expected_state={
            "rule_type": "equals",
            "subject_type": "device",
            "field_name": "serial",
            "risk_score": 80,
        },
    )
    return Policy.create("Inventory Policy", rules=(rule,))


def _orchestration_engine(
    session: Session, *, inventory_service: FakeInventoryService | None = None
) -> OrchestrationEngine:
    workflow = WorkflowEngine(
        inventory_service=inventory_service or FakeInventoryService(_netbox_snapshot()),
        discovery_coordinator=DiscoveryCoordinator(
            FakeCollectorRuntime(_live_snapshot())
        ),
        comparison_engine=ComparisonEngine(),
        evaluation_engine=EvaluationEngine(),
        unit_of_work_factory=lambda: PersistenceUnitOfWork(session),
    )
    return OrchestrationEngine(workflow)


def _context(
    *, max_attempts: int = 1, cancellation_token: JobCancellationToken | None = None
) -> OrchestrationContext:
    return OrchestrationContext(
        collector_contexts=(
            CollectorRuntimeContext(
                target=DiscoveryTarget(identifier="switch-01", address="10.0.0.1")
            ),
        ),
        policies=(_policy(),),
        metadata={"site": "HQ", "device_role": "access", "platform": "iosxe"},
        max_attempts=max_attempts,
        retry_delay_seconds=0.0,
        force_netbox_refresh=False,
        cancellation_token=cancellation_token or CancellationToken(),
    )


@pytest.mark.anyio
async def test_job_lifecycle_runs_and_completes(session: Session) -> None:
    repository = InMemoryJobRepository()
    recorder = EventRecorder()
    manager = JobManager(
        engine=_orchestration_engine(session),
        repository=repository,
        event_publisher=recorder,
        worker_count=1,
    )
    await manager.start_workers()

    request = JobRequest(context=_context())
    submission = await manager.submit_job(request)

    assert submission.queued is True
    assert submission.job.state.status == JobStatus.QUEUED
    assert await repository.get(submission.job.id) is not None

    await asyncio.sleep(0.2)
    await manager.shutdown()

    job = await repository.get(submission.job.id)
    assert job is not None
    assert job.state.status == JobStatus.COMPLETED
    assert JobNotificationEventNames().JOB_COMPLETED in recorder.names


@pytest.mark.anyio
async def test_job_cancellation(session: Session) -> None:
    repository = InMemoryJobRepository()
    recorder = EventRecorder()
    token = JobCancellationToken()
    manager = JobManager(
        engine=_orchestration_engine(session),
        repository=repository,
        event_publisher=recorder,
        worker_count=1,
    )
    await manager.start_workers()

    request = JobRequest(context=_context(cancellation_token=token))
    submission = await manager.submit_job(request)
    await manager.cancel_job(str(submission.job.id), reason="user requested")
    await asyncio.sleep(0.2)
    await manager.shutdown()

    job = await repository.get(submission.job.id)
    assert job is not None
    assert job.state.status in (JobStatus.CANCELLED, JobStatus.COMPLETED)
    assert JobNotificationEventNames().JOB_CANCELLED in recorder.names


@pytest.mark.anyio
async def test_job_retry_and_timeout_support(session: Session) -> None:
    repository = InMemoryJobRepository()
    manager = JobManager(
        engine=_orchestration_engine(
            session,
            inventory_service=FakeInventoryService(_netbox_snapshot(), fail_once=True),
        ),
        repository=repository,
        worker_count=1,
    )
    await manager.start_workers()

    request = JobRequest(context=_context(max_attempts=2), timeout_seconds=5.0)
    submission = await manager.submit_job(request)
    await asyncio.sleep(0.2)
    await manager.shutdown()

    job = await repository.get(submission.job.id)
    assert job is not None
    assert job.state.attempts >= 1


@pytest.mark.anyio
async def test_job_queue_priority_ordering() -> None:
    from backend.app.jobs import Job, JobQueue

    queue = JobQueue()
    low_priority = Job(request=JobRequest(context=_context(), priority=10))
    high_priority = Job(request=JobRequest(context=_context(), priority=1))

    await queue.put(low_priority)
    await queue.put(high_priority)

    first = await queue.get()
    second = await queue.get()

    assert first.request.priority == 1
    assert second.request.priority == 10


@pytest.mark.anyio
async def test_job_concurrency_with_multiple_workers() -> None:
    from backend.app.jobs import InMemoryJobRepository, JobManager
    from backend.app.orchestration.results import OrchestrationResult

    class FakeWorkflow:
        async def execute(self, job: object) -> OrchestrationResult:
            await asyncio.sleep(0.05)
            return OrchestrationResult(
                job_id=job.id,
                run_id=job.context.run_id,
                status=OrchestrationStatus.SUCCEEDED,
                metrics={},
            )

    repository = InMemoryJobRepository()
    manager = JobManager(
        engine=OrchestrationEngine(workflow=FakeWorkflow()),
        repository=repository,
        worker_count=2,
        max_concurrent_jobs=2,
    )
    await manager.start_workers()

    requests = [JobRequest(context=_context()) for _ in range(3)]
    await asyncio.gather(*(manager.submit_job(request) for request in requests))

    await asyncio.sleep(0.3)
    await manager.shutdown()

    assert manager.metrics.started_jobs == 3
    assert all(
        job.state.status == JobStatus.COMPLETED for job in await repository.list_jobs()
    )
