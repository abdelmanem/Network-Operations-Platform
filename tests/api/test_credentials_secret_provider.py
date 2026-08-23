from __future__ import annotations

from collections.abc import Iterator

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
from backend.app.cli import provision_admin_user
from backend.app.config.settings import Settings
from backend.app.core.application import create_application
from backend.app.models.base import BaseModel
from backend.app.transports.secret_errors import (
    InvalidSecretReferenceError,
    ProviderConfigurationError,
    ProviderPermissionDeniedError,
    ProviderUnavailableError,
    SecretNotFoundError,
    SecretProviderError,
)
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_SECRET_VALUE = "api-secret-must-never-leak"


def _build_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()


def _authorized_client(session: Session) -> tuple[TestClient, dict[str, str]]:
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
        username="admin_secret_provider",
        email="admin-secret@example.com",
        password="StrongPass1!",
        confirm_password="StrongPass1!",
        role_name="admin",
    )
    token_pair = auth_service.authenticate_user("admin_secret_provider", "StrongPass1!")
    headers = {
        "Authorization": f"Bearer {token_pair.access_token}",
        "X-Tenant-ID": "tenant-a",
    }
    return TestClient(app), headers


def _create_ssh_profile(
    client: TestClient, headers: dict[str, str], reference: str
) -> str:
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
            "provider_reference": reference,
        },
        headers=headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    return str(response.json()["profile_id"])


def test_credential_test_endpoint_uses_container_environment_provider(
    monkeypatch,
) -> None:
    monkeypatch.setenv("NOP_SECRET_RADISSON", _SECRET_VALUE)
    session = _build_test_session()
    try:
        client, headers = _authorized_client(session)
        with client:
            profile_id = _create_ssh_profile(client, headers, "Radisson")
            response = client.post(
                f"/api/v1/credentials/profiles/{profile_id}/test",
                json={"transport": "ssh", "target": "10.0.0.10"},
                headers=headers,
            )

        body = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert body["status"] == "success"
        assert _SECRET_VALUE not in str(body)
        assert _SECRET_VALUE not in str(response.content)
        assert isinstance(client.app.state.container.secret_provider, object)
        from backend.app.transports.credentials import EnvironmentSecretProvider

        assert isinstance(
            client.app.state.container.secret_provider, EnvironmentSecretProvider
        )
    finally:
        session.close()


def test_credential_test_endpoint_maps_missing_environment_secret() -> None:
    session = _build_test_session()
    try:
        client, headers = _authorized_client(session)
        with client:
            profile_id = _create_ssh_profile(client, headers, "missing-secret-ref")
            response = client.post(
                f"/api/v1/credentials/profiles/{profile_id}/test",
                json={"transport": "ssh", "target": "10.0.0.10"},
                headers=headers,
            )

        body = response.json()
        assert body["status"] == "secret_not_found"
        assert _SECRET_VALUE not in str(body)
        assert "missing-secret-ref" not in body["message"]
    finally:
        session.close()


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (SecretNotFoundError("Requested secret was not found."), "secret_not_found"),
        (
            ProviderUnavailableError("Secret provider is unavailable."),
            "provider_unavailable",
        ),
        (
            ProviderPermissionDeniedError("Secret provider denied access."),
            "provider_permission_denied",
        ),
        (
            InvalidSecretReferenceError("Secret reference is invalid."),
            "invalid_reference",
        ),
        (
            ProviderConfigurationError("Secret provider is not configured."),
            "provider_configuration_error",
        ),
    ],
)
def test_credential_test_endpoint_maps_provider_errors(
    error: SecretProviderError, code: str
) -> None:
    session = _build_test_session()

    class _MappedProvider:
        def resolve_secret(self, _reference: str) -> str:
            raise error

    try:
        client, headers = _authorized_client(session)
        client.app.state.container.secret_provider = _MappedProvider()
        with client:
            profile_id = _create_ssh_profile(client, headers, "Cisco-SW-40-Admin")
            response = client.post(
                f"/api/v1/credentials/profiles/{profile_id}/test",
                json={"transport": "ssh", "target": "10.0.0.10"},
                headers=headers,
            )

        body = response.json()
        assert body["status"] == code
        assert _SECRET_VALUE not in str(body)
        assert _SECRET_VALUE not in body["message"]
    finally:
        session.close()


def test_credential_test_endpoint_never_returns_resolved_secret() -> None:
    session = _build_test_session()

    class _TransientProvider:
        def resolve_secret(self, _reference: str) -> str:
            return _SECRET_VALUE

    try:
        client, headers = _authorized_client(session)
        client.app.state.container.secret_provider = _TransientProvider()
        with client:
            profile_id = _create_ssh_profile(client, headers, "Cisco-SW-40-Automation")
            response = client.post(
                f"/api/v1/credentials/profiles/{profile_id}/test",
                json={"transport": "ssh", "target": "10.0.0.10"},
                headers=headers,
            )

        body = response.json()
        assert body["status"] == "success"
        assert _SECRET_VALUE not in str(body)
        assert "password" not in body
    finally:
        session.close()


def test_production_application_startup_requires_secret_provider() -> None:
    settings = Settings(app_env="production", secret_provider=None)
    with pytest.raises(ProviderConfigurationError) as excinfo:
        create_application(settings)
    assert excinfo.value.code == "provider_configuration_error"


def test_production_application_startup_refuses_environment_provider() -> None:
    settings = Settings(app_env="production", secret_provider="environment")
    with pytest.raises(ProviderConfigurationError) as excinfo:
        create_application(settings)
    assert excinfo.value.code == "provider_configuration_error"
