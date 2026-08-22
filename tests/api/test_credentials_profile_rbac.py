from __future__ import annotations

from collections.abc import Iterator

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
from backend.app.cli import provision_admin_user
from backend.app.core.application import create_application
from backend.app.models.base import BaseModel
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _build_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()


def test_authorized_admin_can_create_a_credential_profile() -> None:
    session = _build_test_session()
    try:
        app = create_application()

        auth_service = AuthenticationService(
            user_repository=SQLAlchemyUserRepository(session),
            role_repository=SQLAlchemyRoleRepository(session),
            permission_repository=SQLAlchemyPermissionRepository(session),
            audit_repository=SQLAlchemyAuditEventRepository(session),
            password_service=PasswordHashingService(),
            token_service=TokenService(secret_key="test-secret"),
        )

        def override_get_db_session() -> Iterator[Session]:
            yield session

        from backend.app.auth.api.dependencies import (
            get_auth_service as get_auth_service_dep,
        )

        app.dependency_overrides[get_db_v1] = override_get_db_session
        app.dependency_overrides[get_db_auth] = override_get_db_session
        app.dependency_overrides[get_auth_service_dep] = lambda: auth_service

        provision_admin_user(
            session,
            username="admin_user",
            email="admin@example.com",
            password="StrongPass1!",
            confirm_password="StrongPass1!",
            role_name="admin",
        )

        token_pair = auth_service.authenticate_user("admin_user", "StrongPass1!")
        headers = {"Authorization": f"Bearer {token_pair.access_token}", "X-Tenant-ID": "tenant-a"}

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/credentials/profiles",
                json={
                    "name": "Cisco SSH",
                    "description": "Cisco SSH login",
                    "vendor": "cisco",
                    "platform": "iosxe",
                    "credential_type": "ssh_password",
                    "username": "netop",
                    "transport_types": ["ssh"],
                    "provider_reference": "env:TEST_CISCO_SSH_PASSWORD",
                },
                headers=headers,
            )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["name"] == "Cisco SSH"
        assert body["provider_reference"] == "env:TEST_CISCO_SSH_PASSWORD"
        assert body["username"] == "netop"
        assert not any(key in body for key in ("password", "secret", "token"))
        assert "super-secret-value" not in str(body)
    finally:
        session.close()


def test_ssh_password_profile_creation_uses_secret_reference_not_secret_field(
    monkeypatch,
) -> None:
    session = _build_test_session()
    monkeypatch.setenv("NOP_SECRET_TEST_CISCO_SSH_PASSWORD", "super-secret-value")
    try:
        app = create_application()

        auth_service = AuthenticationService(
            user_repository=SQLAlchemyUserRepository(session),
            role_repository=SQLAlchemyRoleRepository(session),
            permission_repository=SQLAlchemyPermissionRepository(session),
            audit_repository=SQLAlchemyAuditEventRepository(session),
            password_service=PasswordHashingService(),
            token_service=TokenService(secret_key="test-secret"),
        )

        def override_get_db_session() -> Iterator[Session]:
            yield session

        from backend.app.auth.api.dependencies import (
            get_auth_service as get_auth_service_dep,
        )

        app.dependency_overrides[get_db_v1] = override_get_db_session
        app.dependency_overrides[get_db_auth] = override_get_db_session
        app.dependency_overrides[get_auth_service_dep] = lambda: auth_service

        provision_admin_user(
            session,
            username="admin_ssh_profile",
            email="adminssh@example.com",
            password="StrongPass1!",
            confirm_password="StrongPass1!",
            role_name="admin",
        )
        token_pair = auth_service.authenticate_user("admin_ssh_profile", "StrongPass1!")
        headers = {
            "Authorization": f"Bearer {token_pair.access_token}",
            "X-Tenant-ID": "tenant-a",
        }

        with TestClient(app) as client:
            profile_response = client.post(
                "/api/v1/credentials/profiles",
                json={
                    "name": "Cisco SSH",
                    "description": "Cisco SSH login",
                    "vendor": "cisco",
                    "platform": "iosxe",
                    "credential_type": "ssh_password",
                    "username": "netop",
                    "transport_types": ["ssh"],
                    "provider_reference": "TEST_CISCO_SSH_PASSWORD",
                },
                headers=headers,
            )
            profile_id = profile_response.json()["profile_id"]
            target_response = client.post(
                "/api/v1/discovery/targets",
                json={
                    "identifier": "core-sw-01",
                    "address": "10.0.0.10",
                    "scope_type": "single_device",
                    "tenant_id": "tenant-a",
                    "platform_hint": "cisco-iosxe",
                    "preferred_transport": "ssh",
                    "credential_profile_id": profile_id,
                    "credential_reference": "ignored",
                    "credential_references": {},
                    "allowed_fallback_transports": [],
                    "metadata": {},
                    "enabled": True,
                },
                headers=headers,
            )

        assert profile_response.status_code == status.HTTP_201_CREATED
        profile_body = profile_response.json()
        assert profile_body["provider_reference"] == "TEST_CISCO_SSH_PASSWORD"
        assert not any(key in profile_body for key in ("password", "secret", "token"))
        assert "super-secret-value" not in str(profile_body)

        assert target_response.status_code == status.HTTP_201_CREATED
        target_body = target_response.json()
        assert target_body["credential_profile_id"] == profile_id
        assert "super-secret-value" not in str(target_body)
        assert "TEST_CISCO_SSH_PASSWORD" not in str(target_body)
    finally:
        session.close()


def test_unauthorized_role_receives_403_for_profile_creation() -> None:
    session = _build_test_session()
    try:
        app = create_application()

        auth_service = AuthenticationService(
            user_repository=SQLAlchemyUserRepository(session),
            role_repository=SQLAlchemyRoleRepository(session),
            permission_repository=SQLAlchemyPermissionRepository(session),
            audit_repository=SQLAlchemyAuditEventRepository(session),
            password_service=PasswordHashingService(),
            token_service=TokenService(secret_key="test-secret"),
        )

        role_repo = SQLAlchemyRoleRepository(session)
        perm_repo = SQLAlchemyPermissionRepository(session)
        viewer_role = role_repo.create(name="viewer")
        role_repo.add_permission(viewer_role, perm_repo.create(name="discovery:target:read"))

        auth_service.register_user(
            username="viewer_user",
            email="viewer@example.com",
            password="StrongPass1!",
            roles=[viewer_role.name],
        )
        token_pair = auth_service.authenticate_user("viewer_user", "StrongPass1!")
        headers = {"Authorization": f"Bearer {token_pair.access_token}", "X-Tenant-ID": "tenant-a"}

        def override_get_db_session() -> Iterator[Session]:
            yield session

        from backend.app.auth.api.dependencies import (
            get_auth_service as get_auth_service_dep,
        )

        app.dependency_overrides[get_db_v1] = override_get_db_session
        app.dependency_overrides[get_db_auth] = override_get_db_session
        app.dependency_overrides[get_auth_service_dep] = lambda: auth_service

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/credentials/profiles",
                json={
                    "name": "Viewer profile",
                    "credential_type": "ssh_password",
                    "transport_types": ["ssh"],
                    "provider_reference": "env:VIEWER_SECRET",
                },
                headers=headers,
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        session.close()


def test_profile_creation_requires_authentication() -> None:
    app = create_application()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/credentials/profiles",
            json={
                "name": "Hidden profile",
                "credential_type": "ssh_password",
                "transport_types": ["ssh"],
                "provider_reference": "env:SECRET_TOKEN",
            },
            headers={"X-Tenant-ID": "tenant-a"},
        )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_admin_with_required_permissions_can_list_discovery_and_credentials() -> None:
    session = _build_test_session()
    try:
        app = create_application()

        auth_service = AuthenticationService(
            user_repository=SQLAlchemyUserRepository(session),
            role_repository=SQLAlchemyRoleRepository(session),
            permission_repository=SQLAlchemyPermissionRepository(session),
            audit_repository=SQLAlchemyAuditEventRepository(session),
            password_service=PasswordHashingService(),
            token_service=TokenService(secret_key="test-secret"),
        )

        def override_get_db_session() -> Iterator[Session]:
            yield session

        from backend.app.auth.api.dependencies import (
            get_auth_service as get_auth_service_dep,
        )

        app.dependency_overrides[get_db_v1] = override_get_db_session
        app.dependency_overrides[get_db_auth] = override_get_db_session
        app.dependency_overrides[get_auth_service_dep] = lambda: auth_service

        provision_admin_user(
            session,
            username="admin_reader",
            email="adminreader@example.com",
            password="StrongPass1!",
            confirm_password="StrongPass1!",
            role_name="admin",
        )
        token_pair = auth_service.authenticate_user("admin_reader", "StrongPass1!")
        headers = {"Authorization": f"Bearer {token_pair.access_token}", "X-Tenant-ID": "default"}

        with TestClient(app) as client:
            targets_response = client.get("/api/v1/discovery/targets", headers=headers)
            profiles_response = client.get("/api/v1/credentials/profiles", headers=headers)

        assert targets_response.status_code == status.HTTP_200_OK
        assert profiles_response.status_code == status.HTTP_200_OK
    finally:
        session.close()


def test_discovery_target_uses_profile_reference_without_storing_raw_secret() -> None:
    session = _build_test_session()
    try:
        app = create_application()

        auth_service = AuthenticationService(
            user_repository=SQLAlchemyUserRepository(session),
            role_repository=SQLAlchemyRoleRepository(session),
            permission_repository=SQLAlchemyPermissionRepository(session),
            audit_repository=SQLAlchemyAuditEventRepository(session),
            password_service=PasswordHashingService(),
            token_service=TokenService(secret_key="test-secret"),
        )

        def override_get_db_session() -> Iterator[Session]:
            yield session

        from backend.app.auth.api.dependencies import (
            get_auth_service as get_auth_service_dep,
        )

        app.dependency_overrides[get_db_v1] = override_get_db_session
        app.dependency_overrides[get_db_auth] = override_get_db_session
        app.dependency_overrides[get_auth_service_dep] = lambda: auth_service

        provision_admin_user(
            session,
            username="admin_user2",
            email="admin2@example.com",
            password="StrongPass1!",
            confirm_password="StrongPass1!",
            role_name="admin",
        )
        token_pair = auth_service.authenticate_user("admin_user2", "StrongPass1!")
        headers = {"Authorization": f"Bearer {token_pair.access_token}", "X-Tenant-ID": "tenant-a"}

        profile_response = TestClient(app).post(
            "/api/v1/credentials/profiles",
            json={
                "name": "Cisco SSH",
                "credential_type": "ssh_password",
                "username": "netop",
                "transport_types": ["ssh"],
                "provider_reference": "env:TEST_CISCO_SSH_PASSWORD",
            },
            headers=headers,
        )
        profile_id = profile_response.json()["profile_id"]

        with TestClient(app) as client:
            target_response = client.post(
                "/api/v1/discovery/targets",
                json={
                    "identifier": "core-sw-01",
                    "address": "10.0.0.10",
                    "scope_type": "single_device",
                    "tenant_id": "tenant-a",
                    "platform_hint": "cisco-iosxe",
                    "preferred_transport": "ssh",
                    "credential_profile_id": profile_id,
                    "credential_reference": "ignored",
                    "credential_references": {},
                    "allowed_fallback_transports": [],
                    "metadata": {},
                    "enabled": True,
                },
                headers=headers,
            )

        assert target_response.status_code == status.HTTP_201_CREATED
        target_body = target_response.json()
        assert target_body["credential_profile_id"] == profile_id
        assert "TEST_CISCO_SSH_PASSWORD" not in str(target_body)
        assert "super-secret-value" not in str(target_body)
    finally:
        session.close()
