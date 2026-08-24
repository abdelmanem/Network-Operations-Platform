from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

from backend.app.api.v1.dependencies import get_db_session as get_api_db_session
from backend.app.auth.api.dependencies import (
    get_auth_service as get_auth_service_dependency,
)
from backend.app.auth.api.dependencies import get_db_session as get_auth_db_session
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
from backend.app.config.settings import get_settings
from backend.app.core.application import create_application
from backend.app.models.base import BaseModel
from backend.app.persistence.models import (
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def test_authenticated_discovery_job_list_is_tenant_scoped_and_paginated() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()
    try:
        role_repository = SQLAlchemyRoleRepository(session)
        permission_repository = SQLAlchemyPermissionRepository(session)
        role = role_repository.create(name="discovery-reader")
        permission = permission_repository.create(name="discovery:job:read")
        role_repository.add_permission(role, permission)
        auth_service = AuthenticationService(
            user_repository=SQLAlchemyUserRepository(session),
            role_repository=role_repository,
            permission_repository=permission_repository,
            audit_repository=SQLAlchemyAuditEventRepository(session),
            password_service=PasswordHashingService(),
            token_service=TokenService(secret_key=get_settings().auth_secret_key),
        )
        auth_service.register_user(
            username="discovery-reader",
            email="reader@example.com",
            password="SecurePassword123!",
            roles=[role.name],
        )
        token = auth_service.authenticate_user(
            "discovery-reader", "SecurePassword123!"
        ).access_token

        for tenant_id, count in (("tenant-a", 3), ("tenant-b", 1)):
            for index in range(count):
                target_id, run_id = uuid4(), uuid4()
                session.add_all(
                    [
                        DiscoveryTargetRecord(
                            id=target_id,
                            tenant_id=tenant_id,
                            identifier=f"target-{tenant_id}-{index}",
                            address=f"10.0.{index}.1",
                            credential_reference="profile",
                            metadata_json={},
                        ),
                        DiscoveryRunRecord(
                            id=run_id,
                            tenant_id=tenant_id,
                            target_identifier=f"target-{tenant_id}-{index}",
                            target_address=f"10.0.{index}.1",
                            metadata_json={},
                        ),
                        DiscoveryJobRecord(
                            tenant_id=tenant_id,
                            target_id=target_id,
                            run_id=run_id,
                            state="succeeded",
                            requested_capabilities={},
                        ),
                    ]
                )
        session.commit()

        app = create_application()

        def session_dependency() -> Iterator[Session]:
            yield session

        app.dependency_overrides[get_api_db_session] = session_dependency
        app.dependency_overrides[get_auth_db_session] = session_dependency
        app.dependency_overrides[get_auth_service_dependency] = lambda: auth_service

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/discovery/jobs?page=2&page_size=2",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": "tenant-a",
                },
            )

        assert response.status_code == 200
        assert response.json()["page"] == 2
        assert response.json()["page_size"] == 2
        assert response.json()["total"] == 3
        assert response.json()["has_next"] is False
        assert len(response.json()["items"]) == 1
        assert response.json()["items"][0]["tenant_id"] == "tenant-a"
    finally:
        session.close()
