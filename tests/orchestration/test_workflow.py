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
from backend.app.cache.redis import InMemoryCache
from backend.app.comparison.engine import ComparisonEngine
from backend.app.compliance.domain.enums import RuleStatus
from backend.app.config.settings import get_settings
from backend.app.compliance.policies.models import Policy
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.discovery.context import DiscoveryTarget
from backend.app.evaluation.engine import EvaluationEngine
from backend.app.events.models import BaseEvent
from backend.app.integrations.netbox.mapper import NetBoxInventoryMapper
from backend.app.integrations.netbox.models import (
    NetBoxDevice,
    NetBoxDeviceType,
    NetBoxDeviceTypeReference,
    NetBoxInventoryDataset,
    NetBoxManufacturer,
    NetBoxObjectReference,
    NetBoxRole,
    NetBoxSite,
)
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import Device, DeviceType, Manufacturer
from backend.app.inventory.mapper import InventoryMapper
from backend.app.models.base import BaseModel
from backend.app.services.base import ServiceContext
from backend.app.services.inventory import InventoryService
from backend.app.orchestration import (
    CancellationToken,
    DiscoveryCoordinator,
    OrchestrationContext,
    OrchestrationEngine,
    OrchestrationProgress,
    OrchestrationStatus,
    WorkflowEngine,
)
from backend.app.orchestration.jobs import OrchestrationJob
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


@pytest.mark.anyio
async def test_real_inventory_service_and_workflow_persist_expected_and_observed_state(
    session: Session,
) -> None:
    dataset = NetBoxInventoryDataset(
        sites=(NetBoxSite(id=1, name="HQ", slug="hq"),),
        manufacturers=(NetBoxManufacturer(id=2, name="Cisco", slug="cisco"),),
        device_types=(
            NetBoxDeviceType(
                id=3,
                manufacturer=NetBoxObjectReference(id=2, name="Cisco", slug="cisco"),
                model="WS-C2960X",
                slug="ws-c2960x",
            ),
        ),
        roles=(NetBoxRole(id=4, name="Access", slug="access"),),
        devices=(
            NetBoxDevice(
                id=5,
                name="switch-01",
                device_type=NetBoxDeviceTypeReference(
                    id=3,
                    model="WS-C2960X",
                    slug="ws-c2960x",
                    manufacturer=NetBoxObjectReference(
                        id=2,
                        name="Cisco",
                        slug="cisco",
                    ),
                ),
                role=NetBoxObjectReference(id=4, name="Access", slug="access"),
                serial="ABC123",
            ),
        ),
    )

    class FakeNetBoxService:
        async def fetch_inventory_dataset(self) -> NetBoxInventoryDataset:
            return dataset

    real_inventory = InventoryService(
        context=ServiceContext(settings=get_settings()),
        netbox_service=FakeNetBoxService(),
        inventory_mapper=InventoryMapper(netbox_mapper=NetBoxInventoryMapper()),
        cache=InMemoryCache(),
    )

    workflow = WorkflowEngine(
        inventory_service=real_inventory,
        discovery_coordinator=DiscoveryCoordinator(
            FakeCollectorRuntime(
                LiveInventorySnapshot(
                    devices=(
                        DeviceSnapshot(
                            device_id="switch-01",
                            name="switch-01",
                            model="WS-C2960X",
                            serial_number="XYZ999",
                        ),
                    )
                )
            )
        ),
        comparison_engine=ComparisonEngine(),
        evaluation_engine=EvaluationEngine(),
        unit_of_work_factory=lambda: PersistenceUnitOfWork(session),
    )

    result = await workflow.execute(
        OrchestrationJob(
            context=_context(),
            priority=0,
        )
    )

    assert result.status == OrchestrationStatus.SUCCEEDED
    assert result.netbox_inventory.devices[0].name == "switch-01"
    assert result.live_snapshot.devices[0].device_id == "switch-01"
    assert result.comparison_result is not None
    assert result.comparison_result.metrics.total_differences >= 1
    assert result.discovery_run_id is not None
    assert result.netbox_snapshot_id is not None
    assert result.live_snapshot_id is not None
    assert result.comparison_record_id is not None


@pytest.mark.anyio
async def test_orchestration_supports_cancellation(session: Session) -> None:
    token = CancellationToken()
    progress: list[OrchestrationProgress] = []

    result = await _engine(session).run(
        _context(progress=progress, cancellation_token=token)
    )

    assert result.status == OrchestrationStatus.CANCELLED
    assert result.error_message == "user requested cancellation"


@pytest.mark.anyio
async def test_variance_detection_device_missing_from_live_network(
    session: Session,
) -> None:
    """Test Case A: Device exists in NetBox but is missing from live discovery."""
    netbox_snapshot = NetBoxInventorySnapshot(
        devices=(
            Device(
                name="switch-01",
                device_type=DeviceType(
                    manufacturer=Manufacturer(name="Cisco", slug="cisco"),
                    model="WS-C2960X",
                    slug="ws-c2960x",
                ),
                serial="ABC123",
            ),
        )
    )
    live_snapshot = LiveInventorySnapshot(devices=())

    inventory = FakeInventoryService(netbox_snapshot)
    engine = _engine(
        session,
        inventory_service=inventory,
    )
    runtime = FakeCollectorRuntime(live_snapshot)
    engine.workflow.discovery_coordinator.collector_runtime = runtime

    result = await engine.run(_context())

    assert result.status == OrchestrationStatus.SUCCEEDED
    assert result.comparison_result is not None
    differences = result.comparison_result.differences
    missing_device_diffs = [
        d for d in differences if d.difference_type.value == "missing"
    ]
    assert len(missing_device_diffs) >= 1
    assert any(d.subject_type == "device" for d in missing_device_diffs)
    assert result.comparison_record_id is not None


@pytest.mark.anyio
async def test_variance_detection_device_unexpected_in_live_network(
    session: Session,
) -> None:
    """Test Case B: Device exists in live discovery but not in NetBox."""
    netbox_snapshot = NetBoxInventorySnapshot(devices=())
    live_snapshot = LiveInventorySnapshot(
        devices=(
            DeviceSnapshot(
                device_id="rogue-switch",
                name="rogue-switch",
                model="WS-C2960X",
                serial_number="XYZ999",
            ),
        )
    )

    inventory = FakeInventoryService(netbox_snapshot)
    engine = _engine(
        session,
        inventory_service=inventory,
    )
    runtime = FakeCollectorRuntime(live_snapshot)
    engine.workflow.discovery_coordinator.collector_runtime = runtime

    result = await engine.run(_context())

    assert result.status == OrchestrationStatus.SUCCEEDED
    assert result.comparison_result is not None
    differences = result.comparison_result.differences
    unexpected_diffs = [
        d
        for d in differences
        if d.difference_type.value == "unexpected" and d.subject_type == "device"
    ]
    assert len(unexpected_diffs) >= 1
    assert result.comparison_record_id is not None


@pytest.mark.anyio
async def test_variance_detection_device_attribute_mismatch(
    session: Session,
) -> None:
    """Test Case C: Device exists in both but attributes differ (serial, model, IP)."""
    netbox_snapshot = NetBoxInventorySnapshot(
        devices=(
            Device(
                name="switch-01",
                device_type=DeviceType(
                    manufacturer=Manufacturer(name="Cisco", slug="cisco"),
                    model="WS-C2960X",
                    slug="ws-c2960x",
                ),
                serial="ABC123",
                primary_ip="10.0.0.1",
            ),
        )
    )
    live_snapshot = LiveInventorySnapshot(
        devices=(
            DeviceSnapshot(
                device_id="switch-01",
                name="switch-01",
                model="WS-C2960Y",
                serial_number="XYZ999",
                management_ip="10.0.0.2",
            ),
        )
    )

    inventory = FakeInventoryService(netbox_snapshot)
    engine = _engine(
        session,
        inventory_service=inventory,
    )
    runtime = FakeCollectorRuntime(live_snapshot)
    engine.workflow.discovery_coordinator.collector_runtime = runtime

    result = await engine.run(_context())

    assert result.status == OrchestrationStatus.SUCCEEDED
    assert result.comparison_result is not None
    differences = result.comparison_result.differences
    modified_diffs = [
        d for d in differences if d.difference_type.value == "modified"
    ]
    assert len(modified_diffs) >= 1
    expected_fields = {"serial", "model", "primary_ip"}
    actual_fields = {d.field_name for d in modified_diffs if d.field_name}
    assert actual_fields & expected_fields, (
        f"Expected to find mismatch on {expected_fields}, "
        f"but found {actual_fields}"
    )
    assert result.comparison_record_id is not None


@pytest.mark.anyio
async def test_variance_persistence_enables_historical_comparison(
    session: Session,
) -> None:
    """Test Case D: Verify historical discovery and comparison persistence."""
    manufacturer = Manufacturer(name="Cisco", slug="cisco")
    device_type = DeviceType(
        manufacturer=manufacturer,
        model="WS-C2960X",
        slug="ws-c2960x",
    )

    netbox_snapshot = NetBoxInventorySnapshot(
        devices=(
            Device(
                name="switch-01",
                device_type=device_type,
                serial="ABC123",
            ),
        )
    )
    live_snapshot = LiveInventorySnapshot(
        devices=(
            DeviceSnapshot(
                device_id="switch-01",
                name="switch-01",
                model="WS-C2960X",
                serial_number="ABC123",
            ),
        )
    )

    inventory = FakeInventoryService(netbox_snapshot)
    engine = _engine(session, inventory_service=inventory)
    runtime = FakeCollectorRuntime(live_snapshot)
    engine.workflow.discovery_coordinator.collector_runtime = runtime

    result1 = await engine.run(_context())
    assert result1.status == OrchestrationStatus.SUCCEEDED
    run_id_1 = result1.discovery_run_id
    comparison_id_1 = result1.comparison_record_id

    from backend.app.persistence.repositories import (
        HistoryRepository,
        FindingRepository,
    )

    history_repo = HistoryRepository(session)
    runs = history_repo.list_discovery_runs()
    assert len(runs) >= 1
    assert any(run.id == run_id_1 for run in runs)

    finding_repo = FindingRepository(session)
    result_record = finding_repo.get_comparison_result(comparison_id_1)
    assert result_record is not None
    assert result_record.expected_snapshot_id is not None
    assert result_record.observed_snapshot_id is not None

    result2 = await engine.run(_context())
    assert result2.status == OrchestrationStatus.SUCCEEDED
    run_id_2 = result2.discovery_run_id
    comparison_id_2 = result2.comparison_record_id

    assert run_id_1 != run_id_2
    assert comparison_id_1 != comparison_id_2

    runs = history_repo.list_discovery_runs()
    assert len(runs) >= 2
    assert any(run.id == run_id_2 for run in runs)
