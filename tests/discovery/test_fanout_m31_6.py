import asyncio
from uuid import uuid4

import pytest
from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.contracts import DiscoveryScopeType
from backend.app.discovery.fanout import DiscoveryFanoutService
from backend.app.models.base import BaseModel
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryEvidenceRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
    DiscoveryTransportAttemptRecord,
)
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
    assert len(session.scalars(select(DiscoveryTargetRecord)).all()) == 3  # Root + 2 children

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

