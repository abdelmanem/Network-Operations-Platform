from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from backend.app.api.v1.dependencies import get_db_session as get_db_v1
from backend.app.auth.api.dependencies import get_db_session as get_db_auth
from backend.app.auth.application.services import (
    AuthenticationService,
    PasswordHashingService,
    TokenService,
)
from backend.app.auth.infrastructure.repositories import (
    SQLAlchemyAuditEventRepository,
    SQLAlchemyPermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyUserRepository,
)
from backend.app.core.application import create_application
from backend.app.integrations.netbox.exceptions import (
    NetBoxResponseError,
    NetBoxTransportError,
    NetBoxVersionMismatchError,
)
from backend.app.integrations.netbox.models import NetBoxStatusResponse
from backend.app.models.base import BaseModel
from backend.app.persistence.repositories import SnapshotRepository
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    with session_factory() as session:
        yield session


@pytest.fixture()
def auth_service(db_session: Session) -> AuthenticationService:
    from backend.app.config.settings import get_settings

    return AuthenticationService(
        user_repository=SQLAlchemyUserRepository(db_session),
        role_repository=SQLAlchemyRoleRepository(db_session),
        permission_repository=SQLAlchemyPermissionRepository(db_session),
        audit_repository=SQLAlchemyAuditEventRepository(db_session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key=get_settings().auth_secret_key),
    )


@pytest.fixture()
def client(
    db_session: Session, auth_service: AuthenticationService
) -> Iterator[TestClient]:
    app = create_application()

    def override_get_db_session() -> Iterator[Session]:
        yield db_session

    from backend.app.auth.api.dependencies import (
        get_auth_service as get_auth_service_dep,
    )

    app.dependency_overrides[get_db_v1] = override_get_db_session
    app.dependency_overrides[get_db_auth] = override_get_db_session
    app.dependency_overrides[get_auth_service_dep] = lambda: auth_service
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def writer_token(db_session: Session, auth_service: AuthenticationService) -> str:
    role_repo = SQLAlchemyRoleRepository(db_session)
    perm_repo = SQLAlchemyPermissionRepository(db_session)

    # Setup roles and permissions
    writer_role = role_repo.create(name="writer")
    read_perm = perm_repo.create(name="inventory:read")
    write_perm = perm_repo.create(name="inventory:write")
    role_repo.add_permission(writer_role, read_perm)
    role_repo.add_permission(writer_role, write_perm)

    auth_service.register_user(
        username="writer_user",
        email="writer@example.com",
        password="SecurePassword123!",
        roles=[writer_role.name],
    )
    token_pair = auth_service.authenticate_user("writer_user", "SecurePassword123!")
    return token_pair.access_token


@pytest.fixture()
def reader_token(db_session: Session, auth_service: AuthenticationService) -> str:
    role_repo = SQLAlchemyRoleRepository(db_session)
    perm_repo = SQLAlchemyPermissionRepository(db_session)

    reader_role = role_repo.create(name="reader")
    read_perm = perm_repo.create(name="inventory:read")
    role_repo.add_permission(reader_role, read_perm)

    auth_service.register_user(
        username="reader_user",
        email="reader@example.com",
        password="SecurePassword123!",
        roles=[reader_role.name],
    )
    token_pair = auth_service.authenticate_user("reader_user", "SecurePassword123!")
    return token_pair.access_token


def test_status_endpoint_unauthorized(client: TestClient) -> None:
    response = client.get("/api/v1/integrations/netbox/status")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_status_endpoint_authorized(client: TestClient, reader_token: str) -> None:
    headers = {"Authorization": f"Bearer {reader_token}"}
    response = client.get("/api/v1/integrations/netbox/status", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "configured" in data
    assert "connected" in data
    assert "tls_verified" in data
    assert "inventory_counts" in data


def test_test_connection_endpoint_unauthorized(client: TestClient) -> None:
    response = client.post("/api/v1/integrations/netbox/test")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_test_connection_endpoint_forbidden(
    client: TestClient, reader_token: str
) -> None:
    headers = {"Authorization": f"Bearer {reader_token}"}
    response = client.post("/api/v1/integrations/netbox/test", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.anyio
@patch("backend.app.integrations.netbox.service.NetBoxService.health")
async def test_test_connection_endpoint_success(
    mock_health: MagicMock, client: TestClient, writer_token: str
) -> None:
    mock_health.return_value = NetBoxStatusResponse(
        version="4.6.8",
        api_version="4.6.8",
        hostname="caizhnetbok01",
        status="ok",
    )
    headers = {"Authorization": f"Bearer {writer_token}"}
    response = client.post("/api/v1/integrations/netbox/test", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["connected"] is True
    assert data["version"] == "4.6.8"
    assert data["hostname"] == "caizhnetbok01"


@pytest.mark.anyio
@patch("backend.app.integrations.netbox.service.NetBoxService.health")
async def test_test_connection_endpoint_tls_failure(
    mock_health: MagicMock, client: TestClient, writer_token: str
) -> None:
    mock_health.side_effect = NetBoxTransportError(
        "SSL: CERTIFICATE_VERIFY_FAILED self-signed certificate"
    )
    headers = {"Authorization": f"Bearer {writer_token}"}
    response = client.post("/api/v1/integrations/netbox/test", headers=headers)
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    data = response.json()
    assert data["code"] == "NETBOX_TLS_VALIDATION_FAILED"


@pytest.mark.anyio
@patch("backend.app.integrations.netbox.service.NetBoxService.health")
async def test_test_connection_endpoint_auth_failure(
    mock_health: MagicMock, client: TestClient, writer_token: str
) -> None:
    mock_health.side_effect = NetBoxResponseError(
        status_code=401, endpoint="/api/status/", detail="Unauthorized"
    )
    headers = {"Authorization": f"Bearer {writer_token}"}
    response = client.post("/api/v1/integrations/netbox/test", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert data["code"] == "NETBOX_AUTHENTICATION_FAILED"


@pytest.mark.anyio
@patch("backend.app.integrations.netbox.service.NetBoxService.health")
async def test_test_connection_endpoint_version_mismatch(
    mock_health: MagicMock, client: TestClient, writer_token: str
) -> None:
    mock_health.side_effect = NetBoxVersionMismatchError(
        expected_version="4.6.8", actual_version="4.6.0"
    )
    headers = {"Authorization": f"Bearer {writer_token}"}
    response = client.post("/api/v1/integrations/netbox/test", headers=headers)
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    data = response.json()
    assert data["code"] == "NETBOX_VERSION_MISMATCH"


def test_sync_endpoint_forbidden(client: TestClient, reader_token: str) -> None:
    headers = {"Authorization": f"Bearer {reader_token}"}
    response = client.post("/api/v1/integrations/netbox/sync", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@patch("backend.app.api.v1.integrations.run_netbox_sync_background")
def test_sync_endpoint_success(
    mock_bg_task: MagicMock, client: TestClient, writer_token: str
) -> None:
    headers = {"Authorization": f"Bearer {writer_token}"}
    response = client.post("/api/v1/integrations/netbox/sync", headers=headers)
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_sync_endpoint_concurrency_protection(
    client: TestClient, writer_token: str, db_session: Session
) -> None:
    repo = SnapshotRepository(db_session)
    # Create an active job in the DB
    repo.create_sync_job(uuid4())
    db_session.commit()

    headers = {"Authorization": f"Bearer {writer_token}"}
    response = client.post("/api/v1/integrations/netbox/sync", headers=headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    data = response.json()
    assert data["code"] == "NETBOX_SYNC_ALREADY_RUNNING"
