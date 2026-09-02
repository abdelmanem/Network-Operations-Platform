import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.api.v1.discovery import get_job_evidence
from backend.app.discovery.contracts import DiscoveryJobStatus, DiscoveryScopeType
from backend.app.discovery.fanout import DiscoveryFanoutService
from backend.app.discovery.result_states import DiscoveryResultState
from backend.app.models.base import BaseModel
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryEvidenceRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryRunStatus,
    DiscoveryTargetRecord,
    DiscoveryTransportAttemptRecord,
)
from backend.app.persistence.discovery_repositories import DiscoveryJobRepository
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


class FanoutCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        return None

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        await asyncio.sleep(0.01)
        return {
            "hostname": context.target.identifier,
            "transport": "fake",
            "platform_family": "cisco-iosxe",
        }

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Fan-out must remain raw-evidence only")

    async def close(self) -> None:
        return None


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    return Session(engine)


def _parent(
    session: Session,
    *,
    scope_cidr: str = "192.0.2.0/30",
    identifier: str = "scope-01",
    state: str = "running",
) -> DiscoveryJobRecord:
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier=identifier,
        address=scope_cidr,
        scope_type=DiscoveryScopeType.CIDR_NETWORK.value,
        scope_cidr=scope_cidr,
        enabled=True,
        credential_reference="credential-profile:cisco",
        credential_profile_id="credential-profile:cisco",
        metadata_json={},
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier=identifier,
        target_address=scope_cidr,
        status=DiscoveryRunStatus.STARTED.value,
        metadata_json={},
    )
    session.add_all([target, run])
    session.flush()
    parent = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run.id,
        state=state,
        requested_capabilities={"collector_name": "fanout"},
        attempts=1,
    )
    session.add(parent)
    session.commit()
    return parent


@pytest.mark.anyio
async def test_cidr_fanout_creates_independent_bounded_results() -> None:
    session = _session()
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="Cisco sw 40",
        address="192.0.2.0/30",
        scope_type=DiscoveryScopeType.CIDR_NETWORK.value,
        scope_cidr="192.0.2.0/30",
        enabled=True,
        credential_reference="credential-profile:cisco",
        credential_profile_id="credential-profile:cisco",
        metadata_json={"platform_family": "catalyst-2960x"},
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier="Cisco sw 40",
        status="started",
        metadata_json={},
    )
    session.add_all([target, run])
    session.flush()
    parent = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run.id,
        state="running",
        requested_capabilities={"collector_name": "fanout"},
        attempts=1,
    )
    session.add(parent)
    session.commit()

    registry = CollectorRegistry()
    registry.register(FanoutCollector(name="fanout", capabilities=frozenset()))
    results = await DiscoveryFanoutService(
        session, registry, concurrency=1, max_targets=10
    ).execute(tenant_id="tenant-a", parent_job_id=parent.id)

    assert len(results) == 2
    assert {result.address for result in results} == {"192.0.2.1", "192.0.2.2"}
    assert all(result.state == "succeeded" for result in results)
    assert len(session.scalars(select(DiscoveryDeviceResultRecord)).all()) == 2
    assert len(session.scalars(select(DiscoveryEvidenceRecord)).all()) == 2
    attempts = session.scalars(select(DiscoveryTransportAttemptRecord)).all()
    assert len(attempts) == 2
    assert all(attempt.result == "success" for attempt in attempts)
    assert all(attempt.started_at is not None for attempt in attempts)
    assert all(attempt.completed_at is not None for attempt in attempts)


@pytest.mark.anyio
async def test_cidr_fanout_254_addresses_finalize_durable_summary() -> None:
    session = _session()
    parent = _parent(session, scope_cidr="192.0.2.0/24")
    registry = CollectorRegistry()
    registry.register(FanoutCollector(name="fanout", capabilities=frozenset()))

    results = await DiscoveryFanoutService(
        session, registry, concurrency=20, max_targets=4096
    ).execute(tenant_id="tenant-a", parent_job_id=parent.id)

    assert len(results) == 254
    assert all(result.state == DiscoveryJobStatus.SUCCEEDED.value for result in results)
    run = session.get(DiscoveryRunRecord, parent.run_id)
    assert run is not None
    assert run.status == DiscoveryRunStatus.SUCCEEDED.value
    assert run.total_scanned == 254
    assert run.total_discovered == 254
    assert run.total_partial_discovery == 0
    assert run.total_authentication_failed == 0
    assert run.total_reachable_no_management == 0
    assert run.total_unreachable == 0


def test_durable_reconciliation_counts_mixed_result_states() -> None:
    session = _session()
    parent = _parent(session, scope_cidr="192.0.2.0/29")
    service = DiscoveryFanoutService(session, CollectorRegistry())
    states = (
        DiscoveryResultState.DISCOVERED,
        DiscoveryResultState.PARTIAL_DISCOVERY,
        DiscoveryResultState.AUTHENTICATION_FAILED,
        DiscoveryResultState.REACHABLE_NO_MANAGEMENT,
        DiscoveryResultState.UNREACHABLE,
        DiscoveryResultState.UNREACHABLE,
    )
    for offset, result_state in enumerate(states, start=1):
        child, result = service._create_child(
            "tenant-a",
            session.get(DiscoveryJobRecord, parent.id),  # type: ignore[arg-type]
            session.get(DiscoveryTargetRecord, parent.target_id),  # type: ignore[arg-type]
            f"192.0.2.{offset}",
        )
        result.state = (
            DiscoveryJobStatus.SUCCEEDED.value
            if result_state == DiscoveryResultState.DISCOVERED
            else DiscoveryJobStatus.FAILED.value
        )
        result.result_state = result_state.value
        child.state = result.state
    session.commit()

    DiscoveryFanoutService.reconcile_parent_job(
        session, tenant_id="tenant-a", parent_job_id=parent.id
    )
    run = session.get(DiscoveryRunRecord, parent.run_id)
    assert run is not None
    assert run.total_scanned == 6
    assert run.total_discovered == 1
    assert run.total_authentication_failed == 1
    assert run.total_partial_discovery == 1
    assert run.total_reachable_no_management == 1
    assert run.total_unreachable == 2


def test_durable_reconciliation_is_idempotent() -> None:
    session = _session()
    parent = _parent(session)
    service = DiscoveryFanoutService(session, CollectorRegistry())
    service.reconcile_parent_job(session, tenant_id="tenant-a", parent_job_id=parent.id)
    first = session.get(DiscoveryRunRecord, parent.run_id)
    assert first is not None
    first_counts = (
        first.total_scanned,
        first.total_discovered,
        first.total_unreachable,
        first.total_reachable_no_management,
        first.total_authentication_failed,
        first.total_partial_discovery,
    )
    service.reconcile_parent_job(session, tenant_id="tenant-a", parent_job_id=parent.id)
    second = session.get(DiscoveryRunRecord, parent.run_id)
    assert second is not None
    assert first_counts == (
        second.total_scanned,
        second.total_discovered,
        second.total_unreachable,
        second.total_reachable_no_management,
        second.total_authentication_failed,
        second.total_partial_discovery,
    )
    assert len(session.scalars(select(DiscoveryDeviceResultRecord)).all()) == 2


def test_reconciliation_marks_unexecuted_addresses_cancelled_not_unreachable() -> None:
    session = _session()
    parent = _parent(session)
    DiscoveryFanoutService.reconcile_parent_job(
        session, tenant_id="tenant-a", parent_job_id=parent.id
    )

    results = session.scalars(select(DiscoveryDeviceResultRecord)).all()
    assert len(results) == 2
    assert {result.result_state for result in results} == {
        DiscoveryResultState.CANCELLED.value
    }
    run = session.get(DiscoveryRunRecord, parent.run_id)
    assert run is not None
    assert run.status == DiscoveryRunStatus.FAILED.value
    assert run.total_scanned == 2
    assert run.total_unreachable == 0
    assert run.metadata_json["total_cancelled"] == 2


def test_reconciliation_marks_inflight_children_interrupted() -> None:
    session = _session()
    parent = _parent(session)
    service = DiscoveryFanoutService(session, CollectorRegistry())
    service.reconcile_parent_job(
        session,
        tenant_id="tenant-a",
        parent_job_id=parent.id,
        interrupted=True,
    )

    results = session.scalars(select(DiscoveryDeviceResultRecord)).all()
    assert len(results) == 2
    assert {result.result_state for result in results} == {
        DiscoveryResultState.INTERRUPTED.value
    }
    run = session.get(DiscoveryRunRecord, parent.run_id)
    assert run is not None
    assert run.total_unreachable == 0
    assert run.metadata_json["total_interrupted"] == 2


def test_expired_parent_lease_reconciles_range_run_from_durable_state() -> None:
    session = _session()
    parent = _parent(session)
    owner = uuid4()
    record = session.get(DiscoveryJobRecord, parent.id)
    assert record is not None
    record.execution_owner = owner
    record.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    record.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=2)
    session.commit()

    recovered = DiscoveryJobRepository(session).recover_expired_owned_job(
        tenant_id="tenant-a",
        job_id=parent.id,
        stale_before=datetime.now(UTC),
    )

    assert recovered is not None
    assert recovered.state == DiscoveryJobStatus.FAILED.value
    results = session.scalars(select(DiscoveryDeviceResultRecord)).all()
    assert len(results) == 2
    assert {result.result_state for result in results} == {
        DiscoveryResultState.INTERRUPTED.value
    }
    run = session.get(DiscoveryRunRecord, parent.run_id)
    assert run is not None
    assert run.status == DiscoveryRunStatus.FAILED.value
    assert run.total_scanned == 2
    assert run.total_unreachable == 0


def test_force_cancellation_reconciles_cidr_parent_run_and_results() -> None:
    session = _session()
    parent = _parent(session)
    record = session.get(DiscoveryJobRecord, parent.id)
    assert record is not None
    record.execution_owner = uuid4()
    record.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    record.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=2)
    record.cancellation_requested_at = datetime.now(UTC) - timedelta(minutes=3)
    record.cancellation_requested_by = uuid4()
    record.cancellation_reason = "Force stop fan-out"
    session.commit()

    cancelled = DiscoveryJobRepository(session).resolve_stale_cancellation(
        tenant_id="tenant-a", job_id=parent.id
    )

    assert cancelled.state == DiscoveryJobStatus.CANCELLED.value
    results = session.scalars(select(DiscoveryDeviceResultRecord)).all()
    assert len(results) == 2
    assert {result.state for result in results} == {DiscoveryJobStatus.CANCELLED.value}
    assert {result.result_state for result in results} == {
        DiscoveryResultState.CANCELLED.value
    }
    run = session.get(DiscoveryRunRecord, parent.run_id)
    assert run is not None
    assert run.status == DiscoveryRunStatus.FAILED.value
    assert run.finished_at is not None
    assert run.total_scanned == 2
    assert run.total_unreachable == 0
    assert run.metadata_json["total_cancelled"] == 2


def test_parent_evidence_endpoint_includes_child_evidence() -> None:
    session = _session()
    parent = _parent(session)
    service = DiscoveryFanoutService(session, CollectorRegistry())
    child, _ = service._create_child(
        "tenant-a",
        session.get(DiscoveryJobRecord, parent.id),  # type: ignore[arg-type]
        session.get(DiscoveryTargetRecord, parent.target_id),  # type: ignore[arg-type]
        "192.0.2.1",
    )
    evidence = DiscoveryEvidenceRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        job_id=child.id,
        target_id=child.target_id,
        run_id=child.run_id,
        evidence_type="command_output",
        source="fanout-test",
        collector="fanout-test",
        command_or_probe="show version",
        observed_at=datetime.now(UTC),
        sequence=1,
        payload={"hostname": "router-01"},
        payload_hash="test-hash",
    )
    session.add(evidence)
    session.commit()

    response = get_job_evidence(parent.id, session, object(), "tenant-a")

    assert [item.evidence_id for item in response] == [evidence.id]
    assert response[0].discovery_job_id == child.id


@pytest.mark.anyio
async def test_cidr_fanout_reuses_existing_child_targets_on_rerun() -> None:
    """Verify that re-running the same CIDR target reuses child targets without duplicate-key errors."""
    session = _session()
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="scope-01",
        address="192.0.2.0/30",
        scope_type=DiscoveryScopeType.CIDR_NETWORK.value,
        scope_cidr="192.0.2.0/30",
        enabled=True,
        credential_reference="credential-profile:cisco",
        credential_profile_id="credential-profile:cisco",
        metadata_json={"platform_family": "catalyst-2960x"},
    )
    run1 = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier="scope-01",
        status="started",
        metadata_json={},
    )
    session.add_all([target, run1])
    session.flush()
    parent1 = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run1.id,
        state="running",
        requested_capabilities={"collector_name": "fanout"},
        attempts=1,
    )
    session.add(parent1)
    session.commit()

    registry = CollectorRegistry()
    registry.register(FanoutCollector(name="fanout", capabilities=frozenset()))

    # First run: creates child targets "scope-01:192.0.2.1" and "scope-01:192.0.2.2"
    results1 = await DiscoveryFanoutService(
        session, registry, concurrency=2, max_targets=10
    ).execute(tenant_id="tenant-a", parent_job_id=parent1.id)
    assert len(results1) == 2
    assert (
        len(session.scalars(select(DiscoveryTargetRecord)).all()) == 3
    )  # Root + 2 children

    parent1.state = "succeeded"
    session.commit()

    # Second run for the SAME CIDR target
    run2 = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier="scope-01",
        status="started",
        metadata_json={},
    )
    session.add(run2)
    session.flush()
    parent2 = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run2.id,
        state="running",
        requested_capabilities={"collector_name": "fanout"},
        attempts=1,
    )
    session.add(parent2)
    session.commit()

    # Second execution MUST succeed by reusing the existing targets
    results2 = await DiscoveryFanoutService(
        session, registry, concurrency=2, max_targets=10
    ).execute(tenant_id="tenant-a", parent_job_id=parent2.id)
    assert len(results2) == 2
    assert all(r.state == "succeeded" for r in results2)
    # Total targets remains 3 (1 root + 2 child targets reused, not duplicated)
    assert len(session.scalars(select(DiscoveryTargetRecord)).all()) == 3


@pytest.mark.anyio
async def test_cidr_fanout_synchronizes_stale_existing_child_configuration() -> None:
    session = _session()
    parent_profile_id = str(uuid4())
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="scope-01",
        address="192.0.2.0/30",
        scope_type=DiscoveryScopeType.CIDR_NETWORK.value,
        scope_cidr="192.0.2.0/30",
        enabled=True,
        credential_reference="parent-provider-reference",
        credential_profile_id=parent_profile_id,
        preferred_transport="netmiko",
        platform_hint="cisco-ios",
        metadata_json={"platform_family": "catalyst-2960x"},
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier=target.identifier,
        status="started",
        metadata_json={},
    )
    session.add_all([target, run])
    session.flush()
    existing_child = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="scope-01:192.0.2.1",
        address="192.0.2.1",
        scope_type="single_device",
        enabled=True,
        credential_reference="stale-provider-reference",
        credential_profile_id=str(uuid4()),
        preferred_transport="snmp",
        platform_hint="stale-platform",
        metadata_json={"stale": True},
    )
    session.add(existing_child)
    session.flush()
    parent = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run.id,
        state="running",
        requested_capabilities={"collector_name": "fanout"},
        attempts=1,
    )
    session.add(parent)
    session.commit()

    registry = CollectorRegistry()
    registry.register(FanoutCollector(name="fanout", capabilities=frozenset()))
    results = await DiscoveryFanoutService(
        session, registry, concurrency=1, max_targets=10
    ).execute(tenant_id="tenant-a", parent_job_id=parent.id)

    synchronized = session.get(DiscoveryTargetRecord, existing_child.id)
    assert synchronized is not None
    assert synchronized.tenant_id == "tenant-a"
    assert synchronized.identifier == "scope-01:192.0.2.1"
    assert synchronized.address == "192.0.2.1"
    assert synchronized.credential_profile_id == parent_profile_id
    assert synchronized.credential_reference == "parent-provider-reference"
    assert synchronized.preferred_transport == "netmiko"
    assert synchronized.platform_hint == "cisco-ios"
    assert len(results) == 2
