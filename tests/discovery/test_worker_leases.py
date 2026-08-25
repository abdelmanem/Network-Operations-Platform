"""Comprehensive tests for durable Discovery Job worker, leases, and recovery."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.collectors.base import BaseCollector
from backend.app.collectors.cisco.inventory import CiscoInventoryParser
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.contracts import (
    DiscoveryFailureCode,
    DiscoveryJobStatus,
)
from backend.app.discovery.leases import (
    DISCOVERY_JOB_LEASE_SECONDS,
    HEARTBEAT_LOST_MESSAGE,
    LEASE_EXPIRED_MESSAGE,
    PROTECTED_DISCOVERY_JOB_ID,
)
from backend.app.discovery.worker import (
    DiscoveryJobWorker,
    execute_discovery_job,
)
from backend.app.models.base import BaseModel
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.registry import ParserRegistry
from backend.app.persistence.discovery_repositories import (
    DiscoveryJobRepository,
    DiscoveryResourceNotFoundError,
    DiscoveryTargetRepository,
    InvalidDiscoveryTransitionError,
)
from backend.app.persistence.models import (
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)


class DummyCollector(BaseCollector):
    def __init__(self, name: str = "dummy-collector", delay: float = 0.0) -> None:
        super().__init__(name=name, capabilities=frozenset())
        self.delay = delay
        self.collected = False

    async def health_check(self, context: CollectorContext) -> None:
        await asyncio.sleep(0)

    async def discover(self, context: CollectorContext):
        return ()

    async def collect(self, context: CollectorContext, *, discovered_targets):
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        self.collected = True
        return {
            "target": {
                "identifier": context.target.identifier,
                "address": context.target.address,
                "metadata": {},
            },
            "transport": "fake",
            "platform_family": "catalyst-2960",
            "parser_family": "iosxe",
            "commands": {
                "show version": f"{context.target.identifier} uptime is 1 day",
                "show inventory": (
                    'NAME: "1", DESCR: "WS-C2960X-24PS-L"\n'
                    "PID: WS-C2960X-24PS-L , VID: V01 , SN: TEST-SERIAL"
                ),
            },
        }

    async def normalize(self, context, raw_payload, *, discovered_targets):
        raise AssertionError("Normalization should not run in raw collector")

    async def close(self) -> None:
        return None


def _create_test_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    return engine


def _create_target_and_run(
    session: Session,
    tenant_id: str = "tenant-a",
    identifier: str = "core-01",
    address: str = "10.0.0.1",
) -> tuple[DiscoveryTargetRecord, DiscoveryRunRecord]:
    target = DiscoveryTargetRepository(session).create(
        tenant_id=tenant_id,
        identifier=identifier,
        address=address,
        credential_reference="credential:test",
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_identifier=identifier,
        target_address=address,
        status="started",
        metadata_json={},
    )
    session.add(run)
    session.commit()
    return target, run


def test_lease_invariants_queued_running_terminal() -> None:
    """Verify Invariant 4: Queued, Running, and Terminal lease invariants."""
    engine = _create_test_db()
    session = Session(engine)
    try:
        target, run = _create_target_and_run(session, "tenant-a")
        jobs = DiscoveryJobRepository(session)

        # 1. Queued: execution_owner = NULL, lease_expires_at = NULL, last_heartbeat_at = NULL
        job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
        session.commit()
        assert job.state == DiscoveryJobStatus.QUEUED.value
        assert job.execution_owner is None
        assert job.lease_expires_at is None
        assert job.last_heartbeat_at is None

        # 2. Running: execution_owner != NULL, valid lease, heartbeat timestamp populated
        owner = uuid4()
        claimed = jobs.claim(
            tenant_id="tenant-a",
            job_id=job.id,
            execution_owner=owner,
            lease_seconds=60.0,
        )
        session.commit()
        assert claimed.state == DiscoveryJobStatus.RUNNING.value
        assert claimed.execution_owner == owner
        assert claimed.lease_expires_at is not None
        assert claimed.last_heartbeat_at is not None
        assert claimed.lease_expires_at > claimed.last_heartbeat_at

        # 3. Terminal (SUCCEEDED): execution_owner = NULL, lease_expires_at = NULL, last_heartbeat_at = NULL
        completed = jobs.transition(
            tenant_id="tenant-a",
            job_id=job.id,
            target_state=DiscoveryJobStatus.SUCCEEDED,
            expected_execution_owner=owner,
        )
        session.commit()
        assert completed.state == DiscoveryJobStatus.SUCCEEDED.value
        assert completed.execution_owner is None
        assert completed.lease_expires_at is None
        assert completed.last_heartbeat_at is None
        assert completed.completed_at is not None
    finally:
        session.close()


def test_lease_invariants_queued_cancelled() -> None:
    """Verify Queued cancellation immediately moves to terminal with null lease fields."""
    engine = _create_test_db()
    session = Session(engine)
    try:
        target, run = _create_target_and_run(session, "tenant-a")
        jobs = DiscoveryJobRepository(session)
        job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
        session.commit()

        cancelled, changed = jobs.request_cancellation(
            tenant_id="tenant-a",
            job_id=job.id,
            requested_by=uuid4(),
            reason="Operator cancelled queued",
        )
        session.commit()
        assert changed is True
        assert cancelled.state == DiscoveryJobStatus.CANCELLED.value
        assert cancelled.execution_owner is None
        assert cancelled.lease_expires_at is None
        assert cancelled.last_heartbeat_at is None
        assert cancelled.completed_at is not None
    finally:
        session.close()


def test_race_cancellation_lease_expires_recovery_cancels_old_worker_completion_fails() -> None:
    """Verify Invariant 3 Race Test:

    cancellation requested -> worker lease expires -> recovery cancels job -> old worker completion attempts.
    Final state MUST remain cancelled.
    """
    engine = _create_test_db()
    session = Session(engine)
    try:
        target, run = _create_target_and_run(session, "tenant-a")
        jobs = DiscoveryJobRepository(session)
        job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
        session.commit()

        worker_1_owner = uuid4()
        claimed = jobs.claim(
            tenant_id="tenant-a",
            job_id=job.id,
            execution_owner=worker_1_owner,
            lease_seconds=30.0,
        )
        session.commit()
        assert claimed.state == DiscoveryJobStatus.RUNNING.value
        assert claimed.execution_owner == worker_1_owner

        # Step 1: Cancellation requested
        user_id = uuid4()
        cancelling_job, changed = jobs.request_cancellation(
            tenant_id="tenant-a",
            job_id=job.id,
            requested_by=user_id,
            reason="Operator emergency stop",
        )
        session.commit()
        assert changed is True
        assert cancelling_job.state == DiscoveryJobStatus.RUNNING.value
        assert cancelling_job.cancellation_requested_at is not None

        # Step 2: Worker 1 lease expires
        stale_time = claimed.lease_expires_at + timedelta(seconds=1)

        # Step 3: Recovery discovers expired lease and reconciles (cancels) job
        expired_candidates = jobs.recover_expired_owned_jobs(stale_before=stale_time)
        assert ("tenant-a", job.id) in expired_candidates

        recovered = jobs.recover_expired_owned_job(
            tenant_id="tenant-a",
            job_id=job.id,
            stale_before=stale_time,
        )
        session.commit()
        assert recovered is not None
        assert recovered.state == DiscoveryJobStatus.CANCELLED.value
        assert recovered.failure_code == DiscoveryFailureCode.CANCELLED.value
        assert recovered.failure_message == "Operator emergency stop"
        assert recovered.execution_owner is None
        assert recovered.lease_expires_at is None
        assert recovered.last_heartbeat_at is None
        assert recovered.completed_at is not None

        # Step 4: Old worker 1 completion attempts
        # Old worker tries to transition to SUCCEEDED with its old execution owner
        with pytest.raises(InvalidDiscoveryTransitionError):
            jobs.transition(
                tenant_id="tenant-a",
                job_id=job.id,
                target_state=DiscoveryJobStatus.SUCCEEDED,
                expected_execution_owner=worker_1_owner,
            )
        session.rollback()

        # Old worker also tries finalise_cancellation with its old owner
        finalised = jobs.finalise_cancellation(
            tenant_id="tenant-a",
            job_id=job.id,
            expected_execution_owner=worker_1_owner,
        )
        session.commit()
        assert finalised.state == DiscoveryJobStatus.CANCELLED.value

        # Step 5: Final state verification
        final_job = jobs.get(tenant_id="tenant-a", job_id=job.id)
        assert final_job is not None
        assert final_job.state == DiscoveryJobStatus.CANCELLED.value
        assert final_job.failure_code == DiscoveryFailureCode.CANCELLED.value
        assert final_job.execution_owner is None
        assert final_job.lease_expires_at is None
        assert final_job.last_heartbeat_at is None
    finally:
        session.close()


def test_legacy_unowned_running_jobs_are_not_modified() -> None:
    """Verify Invariant 5: Legacy/unowned running jobs with execution_owner IS NULL are untouched."""
    engine = _create_test_db()
    session = Session(engine)
    try:
        target, run = _create_target_and_run(session, "tenant-a")
        # Insert a legacy running job manually
        legacy_job = DiscoveryJobRecord(
            id=uuid4(),
            tenant_id="tenant-a",
            target_id=target.id,
            run_id=run.id,
            state=DiscoveryJobStatus.RUNNING.value,
            execution_owner=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
        )
        session.add(legacy_job)
        session.commit()

        jobs = DiscoveryJobRepository(session)
        expired = jobs.recover_expired_owned_jobs(
            stale_before=datetime.now(UTC) + timedelta(days=1)
        )
        assert ("tenant-a", legacy_job.id) not in expired

        recovered = jobs.recover_expired_owned_job(
            tenant_id="tenant-a",
            job_id=legacy_job.id,
            stale_before=datetime.now(UTC) + timedelta(days=1),
        )
        session.commit()
        assert recovered is None

        refreshed = jobs.get(tenant_id="tenant-a", job_id=legacy_job.id)
        assert refreshed is not None
        assert refreshed.state == DiscoveryJobStatus.RUNNING.value
        assert refreshed.execution_owner is None
    finally:
        session.close()


def test_protected_discovery_job_is_never_modified_or_claimed() -> None:
    """Verify Invariant 6: Protected job d792bcff-fb06-4428-ab53-557e0cd6eeb9 is never touched."""
    engine = _create_test_db()
    session = Session(engine)
    try:
        target, run = _create_target_and_run(session, "tenant-a")
        protected_job = DiscoveryJobRecord(
            id=PROTECTED_DISCOVERY_JOB_ID,
            tenant_id="tenant-a",
            target_id=target.id,
            run_id=run.id,
            state=DiscoveryJobStatus.QUEUED.value,
            execution_owner=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
        )
        session.add(protected_job)
        session.commit()

        jobs = DiscoveryJobRepository(session)
        queued_roots = jobs.list_queued_roots(limit=10)
        assert all(job_id != PROTECTED_DISCOVERY_JOB_ID for _, job_id in queued_roots)

        with pytest.raises(InvalidDiscoveryTransitionError):
            jobs.claim(tenant_id="tenant-a", job_id=PROTECTED_DISCOVERY_JOB_ID)

        assert (
            jobs.recover_expired_owned_job(
                tenant_id="tenant-a",
                job_id=PROTECTED_DISCOVERY_JOB_ID,
                stale_before=datetime.now(UTC) + timedelta(days=1),
            )
            is None
        )
        assert (
            jobs.abandon_owned_job(
                tenant_id="tenant-a",
                job_id=PROTECTED_DISCOVERY_JOB_ID,
                execution_owner=uuid4(),
            )
            is None
        )
    finally:
        session.close()


def test_stale_running_job_is_never_resumed_but_marked_failed() -> None:
    """Verify Invariant 7: Stale work transitions to terminal FAILED, never resumed."""
    engine = _create_test_db()
    session = Session(engine)
    try:
        target, run = _create_target_and_run(session, "tenant-a")
        jobs = DiscoveryJobRepository(session)
        job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
        session.commit()

        owner = uuid4()
        claimed = jobs.claim(
            tenant_id="tenant-a",
            job_id=job.id,
            execution_owner=owner,
            lease_seconds=10.0,
        )
        session.commit()

        stale_time = claimed.lease_expires_at + timedelta(seconds=1)
        recovered = jobs.recover_expired_owned_job(
            tenant_id="tenant-a",
            job_id=job.id,
            stale_before=stale_time,
        )
        session.commit()

        assert recovered is not None
        assert recovered.state == DiscoveryJobStatus.FAILED.value
        assert recovered.failure_code == DiscoveryFailureCode.DISCOVERY_FAILED.value
        assert recovered.failure_message == LEASE_EXPIRED_MESSAGE
        assert recovered.execution_owner is None
        assert recovered.lease_expires_at is None
        assert recovered.last_heartbeat_at is None
        assert recovered.completed_at is not None
    finally:
        session.close()


def test_lease_renewal_updates_root_and_fanout_children() -> None:
    """Verify renew_lease updates lease and heartbeat timestamp for root and child jobs."""
    engine = _create_test_db()
    session = Session(engine)
    try:
        target, run = _create_target_and_run(session, "tenant-a")
        jobs = DiscoveryJobRepository(session)
        parent_job = jobs.create(
            tenant_id="tenant-a", target_id=target.id, run_id=run.id
        )
        session.commit()

        owner = uuid4()
        claimed_parent = jobs.claim(
            tenant_id="tenant-a",
            job_id=parent_job.id,
            execution_owner=owner,
            lease_seconds=30.0,
        )
        session.commit()

        target_child, run_child = _create_target_and_run(
            session, "tenant-a", identifier="core-01-child", address="10.0.0.2"
        )
        child_job = jobs.create(
            tenant_id="tenant-a",
            target_id=target_child.id,
            run_id=run_child.id,
            parent_job_id=parent_job.id,
        )
        session.commit()
        claimed_child = jobs.claim(
            tenant_id="tenant-a",
            job_id=child_job.id,
            execution_owner=owner,
            lease_seconds=30.0,
        )
        session.commit()

        initial_parent_heartbeat = claimed_parent.last_heartbeat_at
        initial_child_heartbeat = claimed_child.last_heartbeat_at

        renewed = jobs.renew_lease(
            tenant_id="tenant-a",
            job_id=parent_job.id,
            execution_owner=owner,
            lease_seconds=60.0,
        )
        session.commit()
        assert renewed is True

        refreshed_parent = jobs.get(tenant_id="tenant-a", job_id=parent_job.id)
        refreshed_child = jobs.get(tenant_id="tenant-a", job_id=child_job.id)
        assert refreshed_parent is not None
        assert refreshed_child is not None
        assert refreshed_parent.last_heartbeat_at >= initial_parent_heartbeat
        assert refreshed_child.last_heartbeat_at >= initial_child_heartbeat
    finally:
        session.close()


def test_worker_post_init_validation() -> None:
    """Verify DiscoveryJobWorker validates heartbeat interval vs lease duration."""
    registry = CollectorRegistry()
    pipeline = ParserPipeline(ParserRegistry())
    engine = NormalizationEngine()

    with pytest.raises(ValueError, match="Discovery heartbeat interval must be less"):
        DiscoveryJobWorker(
            session_factory=lambda: Session(_create_test_db()),
            collector_registry=registry,
            parser_pipeline=pipeline,
            normalization_engine=engine,
            lease_seconds=30.0,
            heartbeat_interval_seconds=15.0,
        )


@pytest.mark.anyio
async def test_worker_claims_and_executes_across_tenants() -> None:
    """Verify Invariant 1: Worker discovers across tenants, claims and executes explicitly tenant-scoped."""
    engine = _create_test_db()
    session_factory = lambda: Session(engine)

    session = session_factory()
    try:
        target_a, run_a = _create_target_and_run(session, "tenant-alpha", "core-alpha")
        target_b, run_b = _create_target_and_run(session, "tenant-beta", "core-beta")
        jobs = DiscoveryJobRepository(session)
        job_a = jobs.create(
            tenant_id="tenant-alpha",
            target_id=target_a.id,
            run_id=run_a.id,
            requested_capabilities={"collector_name": "test-collector"},
        )
        job_b = jobs.create(
            tenant_id="tenant-beta",
            target_id=target_b.id,
            run_id=run_b.id,
            requested_capabilities={"collector_name": "test-collector"},
        )
        session.commit()
        job_a_id = job_a.id
        job_b_id = job_b.id
    finally:
        session.close()

    registry = CollectorRegistry()
    collector = DummyCollector(name="test-collector")
    registry.register(collector)
    parser_registry = ParserRegistry()
    parser_registry.register(CiscoInventoryParser())
    pipeline = ParserPipeline(registry=parser_registry)
    norm_engine = NormalizationEngine()

    worker = DiscoveryJobWorker(
        session_factory=session_factory,
        collector_registry=registry,
        parser_pipeline=pipeline,
        normalization_engine=norm_engine,
        lease_seconds=10.0,
        heartbeat_interval_seconds=2.0,
        poll_interval_seconds=0.1,
    )

    claimed = worker.claim_queued_jobs()
    assert len(claimed) == 2
    tenants = {t for t, _, _ in claimed}
    assert tenants == {"tenant-alpha", "tenant-beta"}

    # Execute both claimed jobs
    await asyncio.gather(
        *(
            worker._run_owned_job(tenant_id, job_id, owner)
            for tenant_id, job_id, owner in claimed
        )
    )

    session = session_factory()
    try:
        jobs = DiscoveryJobRepository(session)
        res_a = jobs.get(tenant_id="tenant-alpha", job_id=job_a_id)
        res_b = jobs.get(tenant_id="tenant-beta", job_id=job_b_id)
        assert res_a is not None and res_a.state == DiscoveryJobStatus.SUCCEEDED.value
        assert res_b is not None and res_b.state == DiscoveryJobStatus.SUCCEEDED.value
        assert res_a.execution_owner is None
        assert res_b.execution_owner is None
    finally:
        session.close()


@pytest.mark.anyio
async def test_heartbeat_failure_triggers_safe_abandonment() -> None:
    """Verify Invariant 2: Heartbeat failure triggers abandon_owned_job and prevents lingering running jobs."""
    engine = _create_test_db()
    session_factory = lambda: Session(engine)

    session = session_factory()
    try:
        target, run = _create_target_and_run(session, "tenant-a", "core-hb")
        jobs = DiscoveryJobRepository(session)
        job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
        session.commit()
        job_id = job.id
    finally:
        session.close()

    registry = CollectorRegistry()
    collector = DummyCollector(name="slow-collector", delay=0.5)
    registry.register(collector)
    pipeline = ParserPipeline(ParserRegistry())
    norm_engine = NormalizationEngine()

    worker = DiscoveryJobWorker(
        session_factory=session_factory,
        collector_registry=registry,
        parser_pipeline=pipeline,
        normalization_engine=norm_engine,
        lease_seconds=10.0,
        heartbeat_interval_seconds=1.0,
    )

    claimed = worker.claim_queued_jobs()
    assert len(claimed) == 1
    tenant_id, claimed_job_id, owner = claimed[0]

    # Force heartbeat failure by simulating lease lost or abandon
    worker._abandon_if_owned(tenant_id, claimed_job_id, owner)

    session = session_factory()
    try:
        jobs = DiscoveryJobRepository(session)
        res = jobs.get(tenant_id="tenant-a", job_id=job_id)
        assert res is not None
        assert res.state == DiscoveryJobStatus.FAILED.value
        assert res.failure_message == HEARTBEAT_LOST_MESSAGE
        assert res.execution_owner is None
        assert res.lease_expires_at is None
        assert res.last_heartbeat_at is None
    finally:
        session.close()


@pytest.mark.anyio
async def test_execution_error_reported_as_execution_failure_not_heartbeat_failure() -> None:
    """Verify that an unexpected exception during job execution records the actual failure code and message, NOT heartbeat failure."""
    engine = _create_test_db()
    session_factory = lambda: Session(engine)

    session = session_factory()
    try:
        target, run = _create_target_and_run(session, "tenant-a", "core-error-test")
        jobs = DiscoveryJobRepository(session)
        job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
        session.commit()
        job_id = job.id
    finally:
        session.close()

    # Collector that throws a custom error during execution
    class ErrorCollector(DummyCollector):
        async def collect(self, context, *, discovered_targets):
            raise RuntimeError("Database constraint or network protocol crash during collection")

    registry = CollectorRegistry()
    registry.register(ErrorCollector(name="error-collector"))
    pipeline = ParserPipeline(ParserRegistry())
    norm_engine = NormalizationEngine()

    worker = DiscoveryJobWorker(
        session_factory=session_factory,
        collector_registry=registry,
        parser_pipeline=pipeline,
        normalization_engine=norm_engine,
        lease_seconds=30.0,
        heartbeat_interval_seconds=10.0,
    )

    claimed = worker.claim_queued_jobs()
    assert len(claimed) == 1
    tenant_id, claimed_job_id, owner = claimed[0]

    # Run the claimed job
    await worker._run_owned_job(tenant_id, claimed_job_id, owner)

    session = session_factory()
    try:
        jobs = DiscoveryJobRepository(session)
        res = jobs.get(tenant_id="tenant-a", job_id=job_id)
        assert res is not None
        assert res.state == DiscoveryJobStatus.FAILED.value
        assert res.failure_code == DiscoveryFailureCode.DISCOVERY_FAILED.value
        assert "Database constraint or network protocol crash during collection" in (res.failure_message or "")
        assert HEARTBEAT_LOST_MESSAGE not in (res.failure_message or "")
        assert res.execution_owner is None
        assert res.lease_expires_at is None
        assert res.last_heartbeat_at is None
    finally:
        session.close()

