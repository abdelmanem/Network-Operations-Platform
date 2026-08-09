from __future__ import annotations

from uuid import uuid4

import pytest
from backend.app.audit.application.services import AuditService
from backend.app.audit.domain.models import AuditRecord
from backend.app.audit.infrastructure.models import BaseModel
from backend.app.audit.infrastructure.repositories import SQLAlchemyAuditRepository
from backend.app.audit.middleware import AuditMiddleware
from backend.app.auth.application.services import (
    AuthenticationService,
    AuthorizationService,
    PasswordHashingService,
    TokenService,
)
from backend.app.auth.infrastructure.repositories import (
    SQLAlchemyPermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyUserRepository,
)
from backend.app.events.bus import EventBus
from backend.app.events.models import BaseEvent
from backend.app.events.registry import EventHandlerRegistry
from backend.app.policies.lifecycle import PolicyLifecycle
from backend.app.policies.models import Policy, PolicyMetadata, PolicyVersion
from backend.app.policies.service import PolicyService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


@pytest.fixture()
def audit_repo() -> SQLAlchemyAuditRepository:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    return SQLAlchemyAuditRepository(session)


def test_audit_record_is_immutable_and_captures_actor_and_scope() -> None:
    record = AuditRecord.create(
        event_type="policy.updated",
        actor_id=uuid4(),
        tenant_id="site-1",
        resource_type="policy",
        resource_id=str(uuid4()),
        outcome="success",
        metadata={"change": "lifecycle"},
        source="policy",
        category="governance",
    )

    assert record.event_type == "policy.updated"
    assert record.actor_id is not None
    assert record.tenant_id == "site-1"
    assert record.resource_type == "policy"

    with pytest.raises((AttributeError, TypeError)):
        record.event_type = "different"  # type: ignore[attr-defined]


def test_audit_service_sanitizes_sensitive_data_and_records_security_events(
    audit_repo: SQLAlchemyAuditRepository,
) -> None:
    service = AuditService(repository=audit_repo)

    record = service.record_security_event(
        event_type="authentication.failed",
        actor_id=uuid4(),
        request_id="req-1",
        metadata={
            "username": "alice",
            "password": "secret",
            "authorization": "Bearer token",
            "safe": "ok",
        },
    )

    stored = audit_repo.list(limit=5)
    assert len(stored) == 1
    assert stored[0].event_type == "authentication.failed"
    assert "password" not in stored[0].metadata
    assert "authorization" not in stored[0].metadata
    assert stored[0].metadata["safe"] == "ok"
    assert record.request_id == "req-1"


def test_authorization_service_records_denied_access(
    audit_repo: SQLAlchemyAuditRepository,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    user_repo = SQLAlchemyUserRepository(session)
    role_repo = SQLAlchemyRoleRepository(session)
    SQLAlchemyPermissionRepository(session)

    authz_service = AuthorizationService(
        user_repository=user_repo,
        role_repository=role_repo,
        audit_repository=audit_repo,
    )

    user = user_repo.create(
        username="bob",
        email="bob@example.com",
        password_hash="hash",  # noqa: S106
    )

    assert authz_service.authorize(user, "inventory:read") is False
    events = audit_repo.list(limit=5)
    assert events[0].event_type == "authorization.denied"


def test_authentication_service_records_login_and_registration(
    audit_repo: SQLAlchemyAuditRepository,
) -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    user_repo = SQLAlchemyUserRepository(session)
    role_repo = SQLAlchemyRoleRepository(session)
    permission_repo = SQLAlchemyPermissionRepository(session)

    auth_service = AuthenticationService(
        user_repository=user_repo,
        role_repository=role_repo,
        permission_repository=permission_repo,
        audit_repository=audit_repo,
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key="test-secret"),  # noqa: S106
    )

    role = role_repo.create(name="viewer")
    permission = permission_repo.create(name="inventory:read")
    role_repo.add_permission(role, permission)

    auth_service.register_user(
        username="alice",
        email="alice@example.com",
        password="SecureP@ssw0rd!",  # noqa: S106
        roles=[role.name],
    )
    auth_service.authenticate_user("alice", "SecureP@ssw0rd!")

    events = audit_repo.list(limit=10)
    assert {event.event_type for event in events} >= {"user_registered", "login"}


def test_api_middleware_records_safe_api_activity() -> None:
    class RecordingAuditService:
        def __init__(self) -> None:
            self.records: list[AuditRecord] = []

        def record_api_activity(self, **kwargs: object) -> AuditRecord:
            event_type = kwargs.get("event_type", "api.activity")
            record = AuditRecord.create(event_type=event_type, **kwargs)
            self.records.append(record)
            return record

    audit_service = RecordingAuditService()
    app = FastAPI()
    app.add_middleware(AuditMiddleware, audit_service=audit_service)

    @app.get("/inventory")
    def inventory() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get(
        "/inventory",
        headers={"X-Request-ID": "request-123", "X-Tenant-ID": "tenant-7"},
    )

    assert response.status_code == 200
    assert len(audit_service.records) == 1
    assert audit_service.records[0].event_type == "api.activity"
    assert audit_service.records[0].request_id == "request-123"
    assert audit_service.records[0].tenant_id == "tenant-7"


def test_event_bus_integration_records_audit_events(
    audit_repo: SQLAlchemyAuditRepository,
) -> None:
    service = AuditService(repository=audit_repo)
    registry = EventHandlerRegistry()
    event_bus = EventBus(registry=registry)
    service.attach_event_bus(event_bus)

    import asyncio

    asyncio.run(
        event_bus.publish(BaseEvent(name="job.submitted", payload={"job_id": "job-1"}))
    )

    events = audit_repo.list(limit=5)
    assert any(event.event_type == "job.submitted" for event in events)


def test_policy_service_records_policy_changes(
    audit_repo: SQLAlchemyAuditRepository,
) -> None:
    service = AuditService(repository=audit_repo)
    policy_service = PolicyService(audit_service=service)
    policy = Policy.create(
        key="policy-1",
        name="Policy 1",
        version=PolicyVersion.create("1.0.0"),
        lifecycle=PolicyLifecycle.DRAFT,
        metadata=PolicyMetadata(owner="alice"),
    )

    policy_service.record_policy_change(
        policy=policy,
        action="created",
        actor_id=uuid4(),
        tenant_id="tenant-42",
        request_id="policy-req",
    )

    records = audit_repo.list(limit=5)
    assert len(records) == 1
    assert records[0].event_type == "policy.changed"
    assert records[0].resource_id == str(policy.id)
    assert records[0].tenant_id == "tenant-42"
