from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryJobStatus,
    DiscoveryTraceability,
)
from backend.app.models.base import BaseModel
from backend.app.persistence.discovery_repositories import (
    DiscoveryEvidenceRepository,
    DiscoveryJobRepository,
    DiscoveryResourceNotFoundError,
    DiscoveryTargetRepository,
    DuplicateActiveDiscoveryError,
    InvalidDiscoveryTransitionError,
)
from backend.app.persistence.models import DiscoveryRunRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    return Session(engine)


def _target(session: Session, tenant_id: str = "tenant-a"):
    return DiscoveryTargetRepository(session).create(
        tenant_id=tenant_id,
        identifier="core-01",
        address="10.0.0.1",
        credential_reference="credential:network:cisco-prod",
    )


def _run(session: Session, tenant_id: str = "tenant-a") -> DiscoveryRunRecord:
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_identifier="core-01",
        target_address="10.0.0.1",
        status="started",
        metadata_json={},
    )
    session.add(run)
    session.flush()
    return run


def test_target_repository_is_tenant_scoped_and_does_not_store_secret_values(
    session: Session,
) -> None:
    target = _target(session)
    session.commit()
    repository = DiscoveryTargetRepository(session)

    assert repository.get(tenant_id="tenant-a", target_id=target.id) is target
    assert repository.get(tenant_id="tenant-b", target_id=target.id) is None
    assert repository.list(tenant_id="tenant-b") == ()
    assert target.credential_reference == "credential:network:cisco-prod"
    assert not hasattr(target, "password")


def test_target_persists_transport_policy_and_opaque_credential_references(
    session: Session,
) -> None:
    target = DiscoveryTargetRepository(session).create(
        tenant_id="tenant-a",
        identifier="core-02",
        address="10.0.0.2",
        credential_reference="credential:network:default",
        credential_references={"snmp": "credential:network:snmp-prod"},
        allowed_fallback_transports=["ssh", "snmp"],
        vendor="cisco",
        hostname="core-02.example",
    )
    session.commit()

    assert target.vendor == "cisco"
    assert target.hostname == "core-02.example"
    assert target.allowed_fallback_transports == ["ssh", "snmp"]
    assert target.credential_references == {"snmp": "credential:network:snmp-prod"}
    assert "password" not in target.credential_references


def test_job_claim_and_valid_terminal_transition(session: Session) -> None:
    target = _target(session)
    run = _run(session)
    jobs = DiscoveryJobRepository(session)
    job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
    session.commit()

    claimed = jobs.claim(tenant_id="tenant-a", job_id=job.id)
    session.commit()
    assert claimed.state == DiscoveryJobStatus.RUNNING.value
    assert claimed.attempts == 1
    assert claimed.started_at is not None

    completed = jobs.transition(
        tenant_id="tenant-a",
        job_id=job.id,
        target_state=DiscoveryJobStatus.SUCCEEDED,
    )
    session.commit()
    assert completed.state == DiscoveryJobStatus.SUCCEEDED.value
    assert completed.completed_at is not None


def test_job_rejects_invalid_transition_and_tenant_access(session: Session) -> None:
    target = _target(session)
    run = _run(session)
    jobs = DiscoveryJobRepository(session)
    job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
    session.commit()

    assert jobs.get(tenant_id="tenant-b", job_id=job.id) is None
    with pytest.raises(InvalidDiscoveryTransitionError):
        jobs.transition(
            tenant_id="tenant-a",
            job_id=job.id,
            target_state=DiscoveryJobStatus.SUCCEEDED,
        )


def test_only_one_active_job_per_tenant_target(session: Session) -> None:
    target = _target(session)
    first_run = _run(session)
    second_run = _run(session)
    jobs = DiscoveryJobRepository(session)
    jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=first_run.id)
    session.commit()

    with pytest.raises(DuplicateActiveDiscoveryError):
        jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=second_run.id)

    other_tenant_target = _target(session, tenant_id="tenant-b")
    other_tenant_run = _run(session, tenant_id="tenant-b")
    other_job = jobs.create(
        tenant_id="tenant-b",
        target_id=other_tenant_target.id,
        run_id=other_tenant_run.id,
    )
    assert other_job.tenant_id == "tenant-b"


def test_job_creation_rejects_cross_tenant_target_or_run(session: Session) -> None:
    target = _target(session, tenant_id="tenant-a")
    run = _run(session, tenant_id="tenant-b")

    with pytest.raises(DiscoveryResourceNotFoundError):
        DiscoveryJobRepository(session).create(
            tenant_id="tenant-a", target_id=target.id, run_id=run.id
        )


def test_failed_transition_survives_rollback(session: Session) -> None:
    target = _target(session)
    run = _run(session)
    jobs = DiscoveryJobRepository(session)
    job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
    session.commit()
    jobs.claim(tenant_id="tenant-a", job_id=job.id)
    session.commit()

    failed = jobs.mark_failed_after_rollback(
        tenant_id="tenant-a",
        job_id=job.id,
        failure_code="COLLECTOR_FAILED",
        failure_message="Collector failed deterministically.",
    )
    session.commit()
    assert failed.state == DiscoveryJobStatus.FAILED.value
    assert failed.failure_code == "COLLECTOR_FAILED"
    assert failed.failure_message == "Collector failed deterministically."


def test_evidence_is_hash_verified_traceable_and_immutable(session: Session) -> None:
    target = _target(session)
    run = _run(session)
    jobs = DiscoveryJobRepository(session)
    job = jobs.create(tenant_id="tenant-a", target_id=target.id, run_id=run.id)
    session.commit()
    evidence = DiscoveryEvidence(
        traceability=DiscoveryTraceability(
            tenant_id="tenant-a",
            target_id=target.id,
            job_id=job.id,
            discovery_run_id=run.id,
        ),
        collector_name="cisco-iosxe-discovery",
        platform="cisco-iosxe",
        transport="ssh",
        evidence_type="command_output",
        command_or_probe="show version",
        payload={"version": "17.12", "hostname": "core-01"},
        captured_at=datetime.now(UTC),
        sequence=0,
    )
    repository = DiscoveryEvidenceRepository(session)
    record = repository.create(evidence, collector_version="m31.2")
    session.commit()

    assert record.payload_hash == evidence.content_hash
    assert repository.get(tenant_id="tenant-a", evidence_id=record.id) is record
    assert repository.get(tenant_id="tenant-b", evidence_id=record.id) is None

    with pytest.raises(RuntimeError, match="Immutable history"):
        record.payload_hash = "0" * 64
        session.commit()
    session.rollback()

    with pytest.raises(RuntimeError, match="Immutable history"):
        session.delete(record)
        session.commit()


def test_m31_2_migration_is_registered_and_contains_boundary_objects() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("20260819_1200")

    assert revision is not None
    assert revision.module.revision == "20260819_1200"
    migration = Path("alembic/versions/20260819_1200_discovery_persistence.py")
    contents = migration.read_text(encoding="utf-8")
    for table_name in (
        "discovery_targets",
        "discovery_jobs",
        "discovery_evidence",
        "uq_discovery_jobs_active_tenant_target",
    ):
        assert table_name in contents


def test_multi_transport_policy_migration_is_registered() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("20260819_1300")

    assert revision is not None
    assert revision.module.revision == "20260819_1300"
