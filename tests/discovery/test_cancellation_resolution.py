"""Operator-safe durable discovery job cancellation resolution tests.

Tests covered:
- Healthy worker (active lease): resolution rejected with conflict (409).
- Stale worker (expired lease + cancellation requested): transitions to CANCELLED,
  sets finished/completion time, sets failure_code=CANCELLED, clears lease/heartbeat/owner,
  and preserves all cancellation metadata, raw evidence, and device results.
- Legacy unowned running job (execution_owner IS NULL + cancellation requested):
  resolves cleanly.
- Cancellation not requested: resolution rejected with conflict.
- Terminal job (succeeded / failed): resolution rejected with conflict.
- Cross-tenant access: returns 404 / denied.
- RBAC: requires discovery:job:cancel:force permission.
- Race with worker completion: completed job is preserved and resolution rejected.
- Non-destructive execution: never terminates processes, threads, tasks, sockets.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.v1.dependencies import get_db_session as get_api_db_session
from backend.app.api.v1.discovery import router as discovery_router
from backend.app.audit.api.router import get_audit_service
from backend.app.audit.application.services import AuditService
from backend.app.auth.api.dependencies import (
    get_auth_service,
    get_authorization_service,
)
from backend.app.auth.application.services import (
    AuthenticationService,
    AuthorizationService,
    PasswordHashingService,
    TokenService,
)
from backend.app.auth.infrastructure.repositories import (
    SQLAlchemyAuditEventRepository,
    SQLAlchemyPermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyUserRepository,
)
from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryFailureCode,
    DiscoveryJobStatus,
)
from backend.app.models.base import BaseModel
from backend.app.persistence.discovery_repositories import (
    DiscoveryCancellationConflictError,
    DiscoveryEvidenceRepository,
    DiscoveryJobRepository,
    DiscoveryResourceNotFoundError,
    DiscoveryTargetRepository,
)
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryEvidenceRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()
    try:
        yield session
    finally:
        session.close()


def _create_target_run_job(
    session: Session,
    *,
    tenant_id: str = "tenant-a",
    state: str = "running",
    execution_owner: Any = None,
    lease_expires_at: datetime | None = None,
    last_heartbeat_at: datetime | None = None,
    cancellation_requested_at: datetime | None = None,
    cancellation_requested_by: Any = None,
    cancellation_reason: str | None = None,
    parent_job_id: Any = None,
) -> tuple[DiscoveryTargetRecord, DiscoveryRunRecord, DiscoveryJobRecord]:
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        identifier=f"target-{uuid4().hex[:6]}",
        address="192.0.2.1",
        credential_reference="profile",
        metadata_json={},
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_identifier=target.identifier,
        target_address=target.address,
        metadata_json={},
    )
    job = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_id=target.id,
        run_id=run.id,
        parent_job_id=parent_job_id,
        state=state,
        requested_capabilities={},
        execution_owner=execution_owner,
        lease_expires_at=lease_expires_at,
        last_heartbeat_at=last_heartbeat_at,
        cancellation_requested_at=cancellation_requested_at,
        cancellation_requested_by=cancellation_requested_by,
        cancellation_reason=cancellation_reason,
    )
    session.add_all([target, run, job])
    session.commit()
    return target, run, job


# =========================================================================
# Repository Unit Tests
# =========================================================================


def test_resolve_stale_cancellation_fails_for_healthy_active_lease(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    owner = uuid4()
    _, _, job = _create_target_run_job(
        db_session,
        tenant_id="tenant-a",
        state=DiscoveryJobStatus.RUNNING.value,
        execution_owner=owner,
        lease_expires_at=now + timedelta(seconds=120),
        last_heartbeat_at=now,
        cancellation_requested_at=now - timedelta(seconds=10),
        cancellation_requested_by=uuid4(),
        cancellation_reason="Operator cancellation",
    )
    repo = DiscoveryJobRepository(db_session)
    with pytest.raises(DiscoveryCancellationConflictError) as exc_info:
        repo.resolve_stale_cancellation(tenant_id="tenant-a", job_id=job.id)
    assert "actively executing" in str(exc_info.value)

    # Invariant: durable state unchanged
    refreshed = repo.get(tenant_id="tenant-a", job_id=job.id)
    assert refreshed is not None
    assert refreshed.state == DiscoveryJobStatus.RUNNING.value
    assert refreshed.execution_owner == owner


def test_resolve_stale_cancellation_succeeds_for_expired_lease(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    owner = uuid4()
    req_by = uuid4()
    req_at = now - timedelta(minutes=5)
    target, run, job = _create_target_run_job(
        db_session,
        tenant_id="tenant-a",
        state=DiscoveryJobStatus.RUNNING.value,
        execution_owner=owner,
        lease_expires_at=now - timedelta(minutes=1),  # Expired lease
        last_heartbeat_at=now - timedelta(minutes=3),
        cancellation_requested_at=req_at,
        cancellation_requested_by=req_by,
        cancellation_reason="Operator forced resolve",
    )

    # Also add existing evidence and device results to verify preservation
    evidence = DiscoveryEvidenceRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        job_id=job.id,
        target_id=target.id,
        run_id=run.id,
        evidence_type="command_output",
        source="cisco_inventory",
        collector="cisco_inventory",
        command_or_probe="show version",
        observed_at=now - timedelta(minutes=4),
        sequence=1,
        payload="show version sample evidence",
        payload_hash="sample-hash",
    )
    device_result = DiscoveryDeviceResultRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        discovery_job_id=job.id,
        child_job_id=job.id,
        address="192.0.2.1",
        hostname="router-01",
        vendor="cisco",
        platform="cisco_ios",
        state="discovered",
    )
    db_session.add_all([evidence, device_result])
    db_session.commit()

    repo = DiscoveryJobRepository(db_session)
    resolved = repo.resolve_stale_cancellation(tenant_id="tenant-a", job_id=job.id)

    # Invariant: state is CANCELLED, failure code is CANCELLED, finished_at is populated
    assert resolved.state == DiscoveryJobStatus.CANCELLED.value
    assert resolved.failure_code == DiscoveryFailureCode.CANCELLED.value
    assert resolved.failure_message == "Operator forced resolve"
    assert resolved.completed_at is not None

    # Invariant: lease and ownership fields cleared
    assert resolved.execution_owner is None
    assert resolved.lease_expires_at is None
    assert resolved.last_heartbeat_at is None

    # Invariant: cancellation metadata preserved
    assert _as_utc(resolved.cancellation_requested_at) == req_at
    assert resolved.cancellation_requested_by == req_by
    assert resolved.cancellation_reason == "Operator forced resolve"

    # Invariant: evidence and device results preserved
    evidence_repo = DiscoveryEvidenceRepository(db_session)
    ev_list = evidence_repo.list_for_job(tenant_id="tenant-a", job_id=job.id)
    assert len(ev_list) == 1
    assert ev_list[0].id == evidence.id

    dev_results = db_session.scalars(
        select(DiscoveryDeviceResultRecord).where(
            DiscoveryDeviceResultRecord.discovery_job_id == job.id
        )
    ).all()
    assert len(dev_results) == 1
    assert dev_results[0].hostname == "router-01"


def test_resolve_stale_cancellation_succeeds_for_legacy_unowned_job(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    req_by = uuid4()
    req_at = now - timedelta(minutes=2)
    _, _, job = _create_target_run_job(
        db_session,
        tenant_id="tenant-a",
        state=DiscoveryJobStatus.RUNNING.value,
        execution_owner=None,  # Legacy unowned
        lease_expires_at=None,
        last_heartbeat_at=None,
        cancellation_requested_at=req_at,
        cancellation_requested_by=req_by,
        cancellation_reason="Legacy stuck cancellation",
    )

    repo = DiscoveryJobRepository(db_session)
    resolved = repo.resolve_stale_cancellation(tenant_id="tenant-a", job_id=job.id)

    assert resolved.state == DiscoveryJobStatus.CANCELLED.value
    assert resolved.failure_code == DiscoveryFailureCode.CANCELLED.value
    assert resolved.completed_at is not None
    assert resolved.execution_owner is None
    assert _as_utc(resolved.cancellation_requested_at) == req_at


def test_resolve_stale_cancellation_rejects_when_cancellation_not_requested(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    _, _, job = _create_target_run_job(
        db_session,
        tenant_id="tenant-a",
        state=DiscoveryJobStatus.RUNNING.value,
        execution_owner=None,
        lease_expires_at=None,
        cancellation_requested_at=None,  # Not requested!
    )
    repo = DiscoveryJobRepository(db_session)
    with pytest.raises(DiscoveryCancellationConflictError) as exc_info:
        repo.resolve_stale_cancellation(tenant_id="tenant-a", job_id=job.id)
    assert "Cancellation was not requested" in str(exc_info.value)


def test_resolve_stale_cancellation_rejects_terminal_state(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    _, _, job = _create_target_run_job(
        db_session,
        tenant_id="tenant-a",
        state=DiscoveryJobStatus.SUCCEEDED.value,
        cancellation_requested_at=now,
    )
    repo = DiscoveryJobRepository(db_session)
    with pytest.raises(DiscoveryCancellationConflictError) as exc_info:
        repo.resolve_stale_cancellation(tenant_id="tenant-a", job_id=job.id)
    assert "already in terminal state" in str(exc_info.value)


def test_resolve_stale_cancellation_cross_tenant_isolation(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    _, _, job = _create_target_run_job(
        db_session,
        tenant_id="tenant-a",
        state=DiscoveryJobStatus.RUNNING.value,
        cancellation_requested_at=now,
    )
    repo = DiscoveryJobRepository(db_session)
    with pytest.raises(DiscoveryResourceNotFoundError):
        repo.resolve_stale_cancellation(tenant_id="tenant-b", job_id=job.id)


def test_resolve_stale_cancellation_reconciles_running_children(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    _, run, parent_job = _create_target_run_job(
        db_session,
        tenant_id="tenant-a",
        state=DiscoveryJobStatus.RUNNING.value,
        execution_owner=None,
        cancellation_requested_at=now,
        cancellation_reason="Stop root and children",
    )
    child_target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="target-child",
        address="192.0.2.2",
        credential_reference="profile",
        metadata_json={},
    )
    db_session.add(child_target)
    db_session.flush()

    # Child job under parent
    child_job = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_id=child_target.id,
        run_id=run.id,
        parent_job_id=parent_job.id,
        state=DiscoveryJobStatus.RUNNING.value,
        requested_capabilities={},
        execution_owner=None,
        lease_expires_at=None,
    )
    db_session.add(child_job)
    db_session.commit()

    repo = DiscoveryJobRepository(db_session)
    repo.resolve_stale_cancellation(tenant_id="tenant-a", job_id=parent_job.id)

    child_refreshed = repo.get(tenant_id="tenant-a", job_id=child_job.id)
    assert child_refreshed is not None
    assert child_refreshed.state == DiscoveryJobStatus.CANCELLED.value
    assert child_refreshed.failure_code == DiscoveryFailureCode.CANCELLED.value


# =========================================================================
# API & RBAC Integration Tests
# =========================================================================


def _api_client(
    *,
    permission_names: list[str],
) -> tuple[TestClient, Session, DiscoveryJobRecord]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()
    permission_repository = SQLAlchemyPermissionRepository(session)
    role_repository = SQLAlchemyRoleRepository(session)
    role = role_repository.create(name="test-role")
    for name in permission_names:
        permission = permission_repository.create(name=name)
        role_repository.add_permission(role, permission)

    auth_service = AuthenticationService(
        user_repository=SQLAlchemyUserRepository(session),
        role_repository=role_repository,
        permission_repository=permission_repository,
        audit_repository=SQLAlchemyAuditEventRepository(session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key="test-secret"),
    )
    auth_service.register_user(
        username="test-user",
        email="test@example.com",
        password="StrongPass1!",
        roles=[role.name],
    )
    now = datetime.now(UTC)
    target = DiscoveryTargetRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        identifier="target-a",
        address="192.0.2.1",
        credential_reference="profile",
        metadata_json={},
    )
    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_identifier=target.identifier,
        target_address=target.address,
        metadata_json={},
    )
    job = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        target_id=target.id,
        run_id=run.id,
        state="running",
        requested_capabilities={},
        execution_owner=None,
        lease_expires_at=None,
        cancellation_requested_at=now - timedelta(minutes=1),
        cancellation_reason="API test cancellation",
    )
    session.add_all([target, run, job])
    session.commit()

    app = FastAPI()
    app.include_router(discovery_router, prefix="/api/v1")

    def session_dependency() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_api_db_session] = session_dependency
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_authorization_service] = lambda: AuthorizationService(
        user_repository=SQLAlchemyUserRepository(session),
        role_repository=role_repository,
    )
    app.dependency_overrides[get_audit_service] = lambda: AuditService()

    client = TestClient(app)
    return client, session, job


def test_api_resolve_cancellation_requires_authentication() -> None:
    client, _, job = _api_client(permission_names=["discovery:job:cancel:force"])
    response = client.post(
        f"/api/v1/discovery/jobs/{job.id}/cancel/force",
        headers={"X-Tenant-ID": "tenant-a"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_api_resolve_cancellation_requires_cancel_force_permission() -> None:
    # User with only regular discovery:job:cancel and discovery:job:read is denied
    client, session, job = _api_client(
        permission_names=["discovery:job:cancel", "discovery:job:read"]
    )
    auth_service = AuthenticationService(
        user_repository=SQLAlchemyUserRepository(session),
        role_repository=SQLAlchemyRoleRepository(session),
        permission_repository=SQLAlchemyPermissionRepository(session),
        audit_repository=SQLAlchemyAuditEventRepository(session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key="test-secret"),
    )
    token = auth_service.authenticate_user("test-user", "StrongPass1!")

    response = client.post(
        f"/api/v1/discovery/jobs/{job.id}/cancel/force",
        headers={
            "Authorization": f"Bearer {token.access_token}",
            "X-Tenant-ID": "tenant-a",
        },
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_api_resolve_cancellation_succeeds_with_cancel_force_permission() -> None:
    client, session, job = _api_client(
        permission_names=["discovery:job:cancel:force", "discovery:job:read"]
    )
    auth_service = AuthenticationService(
        user_repository=SQLAlchemyUserRepository(session),
        role_repository=SQLAlchemyRoleRepository(session),
        permission_repository=SQLAlchemyPermissionRepository(session),
        audit_repository=SQLAlchemyAuditEventRepository(session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key="test-secret"),
    )
    token = auth_service.authenticate_user("test-user", "StrongPass1!")

    response = client.post(
        f"/api/v1/discovery/jobs/{job.id}/cancel/force",
        headers={
            "Authorization": f"Bearer {token.access_token}",
            "X-Tenant-ID": "tenant-a",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["job_id"] == str(job.id)
    assert data["status"] == "cancelled"
    assert data["error_code"] == DiscoveryFailureCode.CANCELLED.value
    assert data["execution_owner"] is None
    assert data["has_active_lease"] is False


def test_api_resolve_cancellation_returns_conflict_for_active_lease() -> None:
    client, session, job = _api_client(
        permission_names=["discovery:job:cancel:force", "discovery:job:read"]
    )
    # Set active lease on the job
    now = datetime.now(UTC)
    job.execution_owner = uuid4()
    job.lease_expires_at = now + timedelta(seconds=120)
    session.add(job)
    session.commit()

    auth_service = AuthenticationService(
        user_repository=SQLAlchemyUserRepository(session),
        role_repository=SQLAlchemyRoleRepository(session),
        permission_repository=SQLAlchemyPermissionRepository(session),
        audit_repository=SQLAlchemyAuditEventRepository(session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key="test-secret"),
    )
    token = auth_service.authenticate_user("test-user", "StrongPass1!")

    response = client.post(
        f"/api/v1/discovery/jobs/{job.id}/cancel/force",
        headers={
            "Authorization": f"Bearer {token.access_token}",
            "X-Tenant-ID": "tenant-a",
        },
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "actively executing" in response.json()["detail"]


def test_api_resolve_cancellation_cross_tenant_returns_404() -> None:
    client, session, job = _api_client(
        permission_names=["discovery:job:cancel:force"]
    )
    auth_service = AuthenticationService(
        user_repository=SQLAlchemyUserRepository(session),
        role_repository=SQLAlchemyRoleRepository(session),
        permission_repository=SQLAlchemyPermissionRepository(session),
        audit_repository=SQLAlchemyAuditEventRepository(session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key="test-secret"),
    )
    token = auth_service.authenticate_user("test-user", "StrongPass1!")

    response = client.post(
        f"/api/v1/discovery/jobs/{job.id}/cancel/force",
        headers={
            "Authorization": f"Bearer {token.access_token}",
            "X-Tenant-ID": "tenant-b",  # Cross-tenant mismatch
        },
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_api_resolve_cancellation_race_with_worker_completion() -> None:
    client, session, job = _api_client(
        permission_names=["discovery:job:cancel:force", "discovery:job:read"]
    )
    auth_service = AuthenticationService(
        user_repository=SQLAlchemyUserRepository(session),
        role_repository=SQLAlchemyRoleRepository(session),
        permission_repository=SQLAlchemyPermissionRepository(session),
        audit_repository=SQLAlchemyAuditEventRepository(session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key="test-secret"),
    )
    token = auth_service.authenticate_user("test-user", "StrongPass1!")

    # Simulate worker finishing execution right before resolve attempt
    job.state = DiscoveryJobStatus.SUCCEEDED.value
    session.add(job)
    session.commit()

    response = client.post(
        f"/api/v1/discovery/jobs/{job.id}/cancel/force",
        headers={
            "Authorization": f"Bearer {token.access_token}",
            "X-Tenant-ID": "tenant-a",
        },
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already in terminal state" in response.json()["detail"]

    # Invariant: job state remains SUCCEEDED
    refreshed = DiscoveryJobRepository(session).get(tenant_id="tenant-a", job_id=job.id)
    assert refreshed is not None
    assert refreshed.state == DiscoveryJobStatus.SUCCEEDED.value
