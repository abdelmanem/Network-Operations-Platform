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
        identifier="scope-01",
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
        target_identifier="scope-01",
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
    attempts = session.scalars(select(DiscoveryTransportAttemptRecord)).all()
    assert len(attempts) == 2
    assert all(attempt.result == "success" for attempt in attempts)
    assert all(attempt.started_at is not None for attempt in attempts)
    assert all(attempt.completed_at is not None for attempt in attempts)
