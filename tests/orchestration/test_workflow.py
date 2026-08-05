from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from backend.app.collectors.execution.result import CollectorExecutionResult
from backend.app.collectors.execution.status import CollectorExecutionStatus
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.job import CollectorJob
from backend.app.comparison.engine import ComparisonEngine
from backend.app.compliance.domain.enums import RuleStatus
from backend.app.compliance.policies.models import Policy
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.discovery.context import DiscoveryTarget
from backend.app.evaluation.engine import EvaluationEngine
from backend.app.events.models import BaseEvent
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import Device, DeviceType, Manufacturer
from backend.app.models.base import BaseModel
from backend.app.orchestration import (
    CancellationToken,
    DiscoveryCoordinator,
    OrchestrationContext,
    OrchestrationEngine,
    OrchestrationProgress,
    OrchestrationStatus,
    WorkflowEngine,
)
from backend.app.orchestration.events import OrchestrationEventNames
from backend.app.persistence.unit_of_work import PersistenceUnitOfWork
from backend.app.snapshot.entities import (
    DeviceSnapshot,
)
from backend.app.snapshot.entities import (
    InventorySnapshot as LiveInventorySnapshot,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "orchestration"


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
        self.started = 0
        self.stopped = 0
        self.submitted = 0

    async def start(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1

    async def submit(
        self,
        context: CollectorRuntimeContext,
        *,
        priority: int = 0,
    ) -> CollectorJob:
        self.submitted += 1
        return CollectorJob(context=context, priority=priority)

    async def run_job(self, job: CollectorJob) -> CollectorExecutionResult:
        context = job.context
        return CollectorExecutionResult(
            job_id=uuid4(),
            collector_name="fake",
            target=context.target,
            status=CollectorExecutionStatus.SUCCEEDED,
            snapshot=self.snapshot,
            attempts=1,
        )


class EventRecorder:
    def __init__(self) -> None:
        self.names: list[str] = []

    async def publish(self, event: BaseEvent) -> None:
        self.names.append(event.name)


@pytest.fixture()
def session() -> Iterator[Session]:
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


def _context(
    *,
    progress: list[OrchestrationProgress] | None = None,
    event_recorder: EventRecorder | None = None,
    cancellation_token: CancellationToken | None = None,
    max_attempts: int = 1,
) -> OrchestrationContext:
    def on_progress(update: OrchestrationProgress) -> None:
        if progress is not None:
            progress.append(update)
        if cancellation_token is not None and update.step == "netbox_inventory":
            cancellation_token.cancel("user requested cancellation")

    return OrchestrationContext(
        collector_contexts=(
            CollectorRuntimeContext(
                target=DiscoveryTarget(identifier="switch-01", address="10.0.0.1")
            ),
        ),
        policies=(_policy(),),
        metadata={"site": "HQ", "device_role": "access", "platform": "iosxe"},
        max_attempts=max_attempts,
        progress_callback=on_progress,
        event_publisher=event_recorder,
        cancellation_token=cancellation_token or CancellationToken(),
    )


def _engine(
    session: Session,
    *,
    inventory_service: FakeInventoryService | None = None,
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


@pytest.mark.anyio
async def test_orchestration_runs_complete_golden_workflow(session: Session) -> None:
    progress: list[OrchestrationProgress] = []
    events = EventRecorder()
    expected = json.loads(
        (FIXTURES / "golden_workflow.json").read_text(encoding="utf-8")
    )

    result = await _engine(session).run(
        _context(progress=progress, event_recorder=events)
    )

    assert result.status == OrchestrationStatus(expected["status"])
    assert result.comparison_result is not None
    assert (
        len(result.comparison_result.differences)
        == expected["expected_difference_count"]
    )
    assert result.evaluation_decision is not None
    assert result.evaluation_decision.risk_score == 80
    assert result.discovery_run_id is not None
    completed_steps = tuple(
        dict.fromkeys(
            update.step
            for update in progress
            if update.message == "Run completed."
            or update.message.startswith("Completed")
        )
    )
    assert list(completed_steps) == expected["progress_steps"]
    assert OrchestrationEventNames().RUN_SUCCEEDED in events.names


@pytest.mark.anyio
async def test_orchestration_retries_transient_failures(session: Session) -> None:
    inventory = FakeInventoryService(_netbox_snapshot(), fail_once=True)

    result = await _engine(session, inventory_service=inventory).run(
        _context(max_attempts=2)
    )

    assert result.status == OrchestrationStatus.SUCCEEDED
    assert inventory.calls == 2
    assert result.metrics["retried_runs"] == 1


@pytest.mark.anyio
async def test_orchestration_returns_failed_result_on_pipeline_error(
    session: Session,
) -> None:
    inventory = FakeInventoryService(_netbox_snapshot(), fail_once=True)

    result = await _engine(session, inventory_service=inventory).run(_context())

    assert result.status == OrchestrationStatus.FAILED
    assert result.error_message == "temporary netbox failure"


@pytest.mark.anyio
async def test_orchestration_supports_cancellation(session: Session) -> None:
    token = CancellationToken()
    progress: list[OrchestrationProgress] = []

    result = await _engine(session).run(
        _context(progress=progress, cancellation_token=token)
    )

    assert result.status == OrchestrationStatus.CANCELLED
    assert result.error_message == "user requested cancellation"
