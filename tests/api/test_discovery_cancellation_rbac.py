"""RBAC regression coverage for durable discovery job cancellation."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

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
from backend.app.models.base import BaseModel
from backend.app.persistence.models import (
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _client(*, permission_names: list[str]) -> tuple[TestClient, Session, str]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()
    permission_repository = SQLAlchemyPermissionRepository(session)
    role_repository = SQLAlchemyRoleRepository(session)
    role = role_repository.create(name="operator")
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
        username="operator",
        email="operator@example.com",
        password="StrongPass1!",
        roles=[role.name],
    )
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
        state="failed",
        requested_capabilities={},
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
        role_repository=SQLAlchemyRoleRepository(session),
    )
    app.dependency_overrides[get_audit_service] = lambda: AuditService()
    return TestClient(app), session, str(job.id)


def test_cancel_permission_reaches_terminal_cancellation_logic() -> None:
    client, session, job_id = _client(permission_names=["discovery:job:cancel"])
    try:
        response = client.post(
            f"/api/v1/discovery/jobs/{job_id}/cancel",
            headers={
                "Authorization": "Bearer "
                + client.app.dependency_overrides[get_auth_service]()
                .authenticate_user("operator", "StrongPass1!")
                .access_token,
                "X-Tenant-ID": "tenant-a",
            },
            json={"reason": "operator requested stop"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Discovery job is already failed."
    finally:
        client.close()
        session.close()


def test_read_and_submit_permissions_do_not_grant_cancellation() -> None:
    client, session, job_id = _client(
        permission_names=["discovery:job:read", "discovery:job:submit"]
    )
    try:
        auth_service = client.app.dependency_overrides[get_auth_service]()
        token = auth_service.authenticate_user("operator", "StrongPass1!").access_token
        response = client.post(
            f"/api/v1/discovery/jobs/{job_id}/cancel",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"},
            json={"reason": "operator requested stop"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Forbidden"
    finally:
        client.close()
        session.close()
