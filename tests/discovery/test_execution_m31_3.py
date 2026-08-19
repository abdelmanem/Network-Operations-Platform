import asyncio
from uuid import uuid4

import pytest
from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.contracts import DiscoveryJobStatus
from backend.app.discovery.execution import DiscoveryExecutionService
from backend.app.models.base import BaseModel
from backend.app.persistence.discovery_repositories import (
    DiscoveryJobRepository,
    DiscoveryPersistenceError,
)
from backend.app.persistence.models import (
    DiscoveryEvidenceRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


class RawCollector(BaseCollector):
    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        await asyncio.sleep(0.01)
        return {
            "hostname": context.target.identifier,
            "transport": "fake",
            "platform_family": "fake-platform",
            "facts": {"serial": "SERIAL-1"},
        }

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("M31.3 must not normalize raw discovery payloads")

    async def close(self) -> None:
        return None


class FailingCollector(RawCollector):
    async def collect(self, context: CollectorContext, *, discovered_targets):
        raise TimeoutError("device discovery timed out")


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    return Session(engine)


def _job(session: Session, collector_name: str = "raw", *, enabled: bool = True):
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="core-01",
        address="10.0.0.1",
        enabled=enabled,
        credential_reference="credential:fake",
        metadata_json={},
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier=target.identifier,
        target_address=target.address,
        status="started",
        metadata_json={},
    )
    session.add_all([target, run])
    session.flush()
    job = DiscoveryJobRepository(session).create(
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run.id,
        requested_capabilities={"collector_name": collector_name},
    )
    session.commit()
    return job


@pytest.mark.anyio
async def test_successful_discovery_persists_raw_evidence_without_snapshot() -> None:
    session = _session()
    job = _job(session)
    registry = CollectorRegistry()
    registry.register(RawCollector(name="raw", capabilities=frozenset()))

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.executed is True
    assert outcome.evidence_count == 1
    assert outcome.job.state == DiscoveryJobStatus.SUCCEEDED.value
    target = session.execute(select(DiscoveryTargetRecord)).scalar_one()
    evidence = session.execute(select(DiscoveryEvidenceRecord)).scalar_one()
    assert target.identifier == "core-01"
    assert evidence.job_id == job.id
    assert evidence.target_id == target.id
    assert evidence.tenant_id == "tenant-a"
    assert outcome.job.selected_transport == "fake"
    assert outcome.job.selected_platform == "fake-platform"


@pytest.mark.anyio
async def test_failed_discovery_persists_stable_timeout_code() -> None:
    session = _session()
    job = _job(session, collector_name="failing")
    registry = CollectorRegistry()
    registry.register(FailingCollector(name="failing", capabilities=frozenset()))

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    assert outcome.job.failure_code == "DISCOVERY_TIMEOUT"
    assert outcome.job.failure_message == "device discovery timed out"


@pytest.mark.anyio
async def test_disabled_target_fails_without_collecting() -> None:
    session = _session()
    job = _job(session, enabled=False)
    registry = CollectorRegistry()
    registry.register(RawCollector(name="raw", capabilities=frozenset()))

    outcome = await DiscoveryExecutionService(session, registry).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    assert outcome.job.failure_code == "TARGET_DISABLED"


@pytest.mark.anyio
async def test_missing_collector_fails_with_unsupported_platform() -> None:
    session = _session()
    job = _job(session, collector_name="missing")

    outcome = await DiscoveryExecutionService(session, CollectorRegistry()).execute(
        tenant_id="tenant-a", job_id=job.id
    )

    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    assert outcome.job.failure_code == "UNSUPPORTED_PLATFORM"


@pytest.mark.anyio
async def test_evidence_persistence_failure_does_not_leave_job_running() -> None:
    session = _session()
    job = _job(session)
    registry = CollectorRegistry()
    registry.register(RawCollector(name="raw", capabilities=frozenset()))
    service = DiscoveryExecutionService(session, registry)

    def fail_evidence(*args, **kwargs):
        raise DiscoveryPersistenceError("evidence store unavailable")

    service.evidence.create = fail_evidence  # type: ignore[method-assign]
    outcome = await service.execute(tenant_id="tenant-a", job_id=job.id)

    assert outcome.job.state == DiscoveryJobStatus.FAILED.value
    assert outcome.job.failure_code == "EVIDENCE_PERSISTENCE_FAILED"
    assert outcome.job.state != DiscoveryJobStatus.RUNNING.value


@pytest.mark.anyio
async def test_same_job_cannot_execute_concurrently_or_duplicate_evidence() -> None:
    session = _session()
    job = _job(session)
    registry = CollectorRegistry()
    registry.register(RawCollector(name="raw", capabilities=frozenset()))
    service = DiscoveryExecutionService(session, registry)

    first, second = await asyncio.gather(
        service.execute(tenant_id="tenant-a", job_id=job.id),
        service.execute(tenant_id="tenant-a", job_id=job.id),
    )

    assert sorted((first.executed, second.executed)) == [False, True]
    assert first.job.state == DiscoveryJobStatus.SUCCEEDED.value
    assert second.job.state == DiscoveryJobStatus.SUCCEEDED.value
    assert first.evidence_count + second.evidence_count == 1


@pytest.mark.anyio
async def test_completed_job_is_idempotent_noop() -> None:
    session = _session()
    job = _job(session)
    registry = CollectorRegistry()
    registry.register(RawCollector(name="raw", capabilities=frozenset()))
    service = DiscoveryExecutionService(session, registry)

    first = await service.execute(tenant_id="tenant-a", job_id=job.id)
    second = await service.execute(tenant_id="tenant-a", job_id=job.id)

    assert first.executed is True
    assert second.executed is False
    assert second.evidence_count == 0
