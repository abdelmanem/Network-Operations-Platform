from __future__ import annotations

from uuid import uuid4

import pytest
from backend.app.api.v1.discovery import cancel_job
from backend.app.auth.domain.models import User
from backend.app.discovery.contracts import DiscoveryFailureCode, DiscoveryJobStatus
from backend.app.models.base import BaseModel
from backend.app.persistence.discovery_repositories import (
    DiscoveryCancellationConflictError,
    DiscoveryJobRepository,
)
from backend.app.persistence.models import (
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)
from backend.app.schemas.discovery import DiscoveryJobCancellationRequest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response


class RecordingAuditService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_api_activity(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def _job(session: Session, *, state: str = "queued") -> DiscoveryJobRecord:
    tenant_id = "tenant-a"
    target = DiscoveryTargetRecord(
        tenant_id=tenant_id,
        identifier=str(uuid4()),
        address="10.0.0.1",
        credential_reference="profile",
        metadata_json={},
    )
    run = DiscoveryRunRecord(
        tenant_id=tenant_id,
        target_identifier=target.identifier,
        target_address=target.address,
        metadata_json={},
    )
    session.add_all([target, run])
    session.flush()
    job = DiscoveryJobRecord(
        tenant_id=tenant_id,
        target_id=target.id,
        run_id=run.id,
        state=state,
        requested_capabilities={},
    )
    session.add(job)
    session.commit()
    return job


def test_queued_cancellation_is_terminal_and_prevents_claim() -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    try:
        job = _job(session)
        repository = DiscoveryJobRepository(session)
        cancelled, changed = repository.request_cancellation(
            tenant_id="tenant-a",
            job_id=job.id,
            requested_by=uuid4(),
            reason="Cancelled by operator",
        )
        session.commit()

        assert changed is True
        assert cancelled.state == DiscoveryJobStatus.CANCELLED.value
        assert cancelled.failure_code == DiscoveryFailureCode.CANCELLED.value
        with pytest.raises(Exception, match="Only queued"):
            repository.claim(tenant_id="tenant-a", job_id=job.id)
    finally:
        session.close()


def test_running_cancellation_is_idempotent_then_finalised() -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    try:
        job = _job(session, state="running")
        repository = DiscoveryJobRepository(session)
        first, changed = repository.request_cancellation(
            tenant_id="tenant-a", job_id=job.id, requested_by=uuid4(), reason="stop"
        )
        session.commit()
        second, changed_again = repository.request_cancellation(
            tenant_id="tenant-a", job_id=job.id, requested_by=uuid4(), reason="other"
        )
        assert first.state == "running"
        assert changed is True
        assert changed_again is False
        assert second.cancellation_reason == "stop"

        cancelled = repository.finalise_cancellation(
            tenant_id="tenant-a", job_id=job.id
        )
        session.commit()
        assert cancelled.state == "cancelled"
    finally:
        session.close()


def test_other_terminal_jobs_cannot_be_cancelled() -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    try:
        job = _job(session, state="succeeded")
        with pytest.raises(DiscoveryCancellationConflictError):
            DiscoveryJobRepository(session).request_cancellation(
                tenant_id="tenant-a", job_id=job.id, requested_by=uuid4(), reason="stop"
            )
    finally:
        session.close()


def test_running_cancellation_response_is_accepted_and_audited() -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    job = _job(session, state="running")
    actor = User(id=uuid4(), username="operator")
    audit = RecordingAuditService()
    response = Response()
    request = Request({"type": "http", "headers": []})
    try:
        result = cancel_job(
            job_id=job.id,
            payload=DiscoveryJobCancellationRequest(reason="operator requested stop"),
            request=request,
            response=response,
            db_session=session,
            user=actor,
            tenant_id="tenant-a",
            audit_service=audit,  # type: ignore[arg-type]
        )

        assert response.status_code == 202
        assert result.status == DiscoveryJobStatus.RUNNING
        assert result.cancellation_requested_by == actor.id
        assert result.cancellation_reason == "operator requested stop"
        assert audit.calls[0]["event_type"] == "discovery.job_cancel_requested"
        assert audit.calls[0]["outcome"] == "requested"
    finally:
        session.close()
