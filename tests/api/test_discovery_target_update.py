from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

from backend.app.api.v1.dependencies import get_db_session as get_db_v1
from backend.app.auth.api.dependencies import (
    get_auth_service as get_auth_service_dep,
    get_db_session as get_db_auth,
)
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
from backend.app.persistence.discovery_repositories import (
    CredentialProfileRepository,
    DiscoveryResourceNotFoundError,
    DiscoveryTargetRepository,
)
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


def _setup_app_and_client(session: Session) -> tuple[TestClient, dict[str, str], AuthenticationService]:
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
    headers = {
        "Authorization": f"Bearer {token_pair.access_token}",
        "X-Tenant-ID": "tenant-a",
    }

    return TestClient(app), headers, auth_service


def test_authorized_user_can_update_discovery_target_credential_profile() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)

        cred_repo = CredentialProfileRepository(session)
        profile_1 = cred_repo.create(
            tenant_id="tenant-a",
            name="Cisco Profile 1",
            provider_reference="env:PROFILE_1_SECRET",
            transport_types=["ssh"],
            username="cisco1",
        )
        profile_2 = cred_repo.create(
            tenant_id="tenant-a",
            name="Cisco Profile 2",
            provider_reference="env:PROFILE_2_SECRET",
            transport_types=["ssh", "netmiko"],
            username="cisco2",
        )

        target_repo = DiscoveryTargetRepository(session)
        target = target_repo.create(
            tenant_id="tenant-a",
            identifier="cisco",
            address="192.168.20.0/24",
            scope_type="cidr_network",
            scope_cidr="192.168.20.0/24",
            platform_hint="cisco-ios",
            preferred_transport="netmiko",
            credential_reference=profile_1.provider_reference,
            credential_profile_id=str(profile_1.id),
        )
        session.commit()

        # Update target to profile_2
        response = client.patch(
            f"/api/v1/discovery/targets/{target.id}",
            json={"credential_profile_id": str(profile_2.id)},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["target_id"] == str(target.id)
        assert data["credential_profile_id"] == str(profile_2.id)

        # Check in DB
        reloaded = target_repo.get(tenant_id="tenant-a", target_id=target.id)
        assert reloaded is not None
        assert reloaded.credential_profile_id == str(profile_2.id)
        assert reloaded.credential_reference == profile_2.provider_reference
    finally:
        session.close()


def test_update_discovery_target_rejects_nonexistent_credential_profile() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)

        cred_repo = CredentialProfileRepository(session)
        profile_1 = cred_repo.create(
            tenant_id="tenant-a",
            name="Cisco Profile 1",
            provider_reference="env:PROFILE_1_SECRET",
            transport_types=["ssh"],
        )

        target_repo = DiscoveryTargetRepository(session)
        target = target_repo.create(
            tenant_id="tenant-a",
            identifier="cisco",
            address="192.168.20.0/24",
            scope_type="cidr_network",
            scope_cidr="192.168.20.0/24",
            credential_reference=profile_1.provider_reference,
            credential_profile_id=str(profile_1.id),
        )
        session.commit()

        fake_id = str(uuid4())
        response = client.patch(
            f"/api/v1/discovery/targets/{target.id}",
            json={"credential_profile_id": fake_id},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

        # Existing target remains unchanged
        reloaded = target_repo.get(tenant_id="tenant-a", target_id=target.id)
        assert reloaded.credential_profile_id == str(profile_1.id)
    finally:
        session.close()


def test_update_discovery_target_rejects_cross_tenant_credential_profile() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)

        cred_repo = CredentialProfileRepository(session)
        profile_a = cred_repo.create(
            tenant_id="tenant-a",
            name="Profile Tenant A",
            provider_reference="env:PROFILE_A",
            transport_types=["ssh"],
        )
        profile_b = cred_repo.create(
            tenant_id="tenant-b",
            name="Profile Tenant B",
            provider_reference="env:PROFILE_B",
            transport_types=["ssh"],
        )

        target_repo = DiscoveryTargetRepository(session)
        target = target_repo.create(
            tenant_id="tenant-a",
            identifier="cisco",
            address="192.168.20.0/24",
            scope_type="cidr_network",
            scope_cidr="192.168.20.0/24",
            credential_reference=profile_a.provider_reference,
            credential_profile_id=str(profile_a.id),
        )
        session.commit()

        # Attempt to use tenant-b profile from tenant-a
        response = client.patch(
            f"/api/v1/discovery/targets/{target.id}",
            json={"credential_profile_id": str(profile_b.id)},
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Existing target remains unchanged
        reloaded = target_repo.get(tenant_id="tenant-a", target_id=target.id)
        assert reloaded.credential_profile_id == str(profile_a.id)
    finally:
        session.close()


def test_update_discovery_target_rejects_incompatible_transport() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)

        cred_repo = CredentialProfileRepository(session)
        ssh_profile = cred_repo.create(
            tenant_id="tenant-a",
            name="SSH Profile",
            provider_reference="env:SSH_KEY",
            transport_types=["ssh"],
        )
        snmp_profile = cred_repo.create(
            tenant_id="tenant-a",
            name="SNMP Only Profile",
            provider_reference="env:SNMP_COMM",
            transport_types=["snmp"],
        )

        target_repo = DiscoveryTargetRepository(session)
        target = target_repo.create(
            tenant_id="tenant-a",
            identifier="cisco",
            address="192.168.20.0/24",
            scope_type="cidr_network",
            scope_cidr="192.168.20.0/24",
            preferred_transport="ssh",
            credential_reference=ssh_profile.provider_reference,
            credential_profile_id=str(ssh_profile.id),
        )
        session.commit()

        # Update target with SNMP-only profile while preferred_transport is ssh
        response = client.patch(
            f"/api/v1/discovery/targets/{target.id}",
            json={"credential_profile_id": str(snmp_profile.id)},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "does not support target transport" in response.json()["detail"]

        # Target remains unchanged
        reloaded = target_repo.get(tenant_id="tenant-a", target_id=target.id)
        assert reloaded.credential_profile_id == str(ssh_profile.id)
    finally:
        session.close()


def test_update_discovery_target_rbac_enforcement() -> None:
    session = _build_test_session()
    try:
        client, _, auth_service = _setup_app_and_client(session)

        # Create a read-only viewer user with only read permission
        user_repo = SQLAlchemyUserRepository(session)
        role_repo = SQLAlchemyRoleRepository(session)
        perm_repo = SQLAlchemyPermissionRepository(session)

        from backend.app.auth.domain.models import Role, Permission
        read_perm = perm_repo.get_by_name("discovery:target:read")
        if not read_perm:
            read_perm = perm_repo.create(Permission(name="discovery:target:read", description="Read discovery targets"))
        viewer_role = role_repo.get_by_name("viewer")
        if not viewer_role:
            viewer_role = role_repo.create(name="viewer", description="Viewer role")
        role_repo.add_permission(viewer_role, read_perm)

        auth_service.register_user(
            username="viewer_user",
            email="viewer@example.com",
            password="StrongPass1!",
            roles=[viewer_role.name],
        )
        session.commit()

        token_pair = auth_service.authenticate_user("viewer_user", "StrongPass1!")
        viewer_headers = {
            "Authorization": f"Bearer {token_pair.access_token}",
            "X-Tenant-ID": "tenant-a",
        }

        cred_repo = CredentialProfileRepository(session)
        profile = cred_repo.create(
            tenant_id="tenant-a",
            name="Cisco Profile",
            provider_reference="env:PROFILE",
            transport_types=["ssh"],
        )
        target_repo = DiscoveryTargetRepository(session)
        target = target_repo.create(
            tenant_id="tenant-a",
            identifier="cisco",
            address="192.168.20.0/24",
            scope_type="cidr_network",
            scope_cidr="192.168.20.0/24",
            credential_reference=profile.provider_reference,
            credential_profile_id=str(profile.id),
        )
        session.commit()

        # Viewer attempts patch
        response = client.patch(
            f"/api/v1/discovery/targets/{target.id}",
            json={"enabled": False},
            headers=viewer_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
    finally:
        session.close()


def test_discovery_target_repository_update_methods() -> None:
    session = _build_test_session()
    try:
        repo = DiscoveryTargetRepository(session)
        target = repo.create(
            tenant_id="tenant-a",
            identifier="test-target",
            address="10.0.0.1",
            credential_reference="ref-1",
            credential_profile_id="prof-1",
        )
        session.commit()

        updated = repo.update(
            tenant_id="tenant-a",
            target_id=target.id,
            platform_hint="cisco-ios",
            preferred_transport="ssh",
            enabled=False,
        )
        assert updated.platform_hint == "cisco-ios"
        assert updated.preferred_transport == "ssh"
        assert updated.enabled is False

        # Attempt to update under wrong tenant raises DiscoveryResourceNotFoundError
        import pytest
        with pytest.raises(DiscoveryResourceNotFoundError):
            repo.update(
                tenant_id="tenant-other",
                target_id=target.id,
                enabled=True,
            )
    finally:
        session.close()
