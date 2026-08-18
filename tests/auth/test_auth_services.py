from __future__ import annotations

import json

from backend.app.auth.application.services import (
    AuthenticationService,
    AuthorizationService,
    PasswordHashingService,
    TokenService,
)
from backend.app.auth.infrastructure.models import AuthAuditEvent, BaseModel
from backend.app.auth.infrastructure.repositories import (
    SQLAlchemyAuditEventRepository,
    SQLAlchemyPermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyUserRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_password_hashing_and_token_round_trip() -> None:
    hashing = PasswordHashingService()
    password = "SecureP@ssw0rd!"  # noqa: S105
    hashed = hashing.hash_password(password)

    assert hashing.verify_password(password, hashed)
    assert not hashing.verify_password("wrong", hashed)

    token_service = TokenService(secret_key="test-secret")  # noqa: S106
    claims = {"sub": "user-1", "type": "access"}
    token = token_service.encode(claims, expires_in_seconds=60)
    decoded = token_service.decode(token)

    assert decoded["sub"] == "user-1"
    assert decoded["type"] == "access"


def test_authentication_and_authorization_flow() -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)

    user_repo = SQLAlchemyUserRepository(session)
    role_repo = SQLAlchemyRoleRepository(session)
    permission_repo = SQLAlchemyPermissionRepository(session)
    audit_repo = SQLAlchemyAuditEventRepository(session)

    hashing = PasswordHashingService()
    token_service = TokenService(secret_key="test-secret")  # noqa: S106
    auth_service = AuthenticationService(
        user_repository=user_repo,
        role_repository=role_repo,
        permission_repository=permission_repo,
        audit_repository=audit_repo,
        password_service=hashing,
        token_service=token_service,
    )
    authz = AuthorizationService(user_repository=user_repo, role_repository=role_repo)

    role = role_repo.create(name="viewer", description="Viewer role")
    permission = permission_repo.create(
        name="inventory:read",
        description="Read inventory",
    )
    role_repo.add_permission(role, permission)

    user = auth_service.register_user(
        username="alice",
        email="alice@example.com",
        password="SecureP@ssw0rd!",  # noqa: S105,S106
        roles=[role.name],
    )
    assert user.username == "alice"

    token_pair = auth_service.authenticate_user("alice", "SecureP@ssw0rd!")  # noqa: S105
    assert token_pair.access_token
    assert token_pair.refresh_token

    current = auth_service.get_current_user(token_pair.access_token)
    assert current is not None
    assert current.username == "alice"

    assert authz.authorize(current, "inventory:read")
    assert not authz.authorize(current, "inventory:write")

    event = audit_repo.list(limit=1)[0]
    assert event.event_type == "login"
    assert event.subject_id == current.id

    session.close()


def test_audit_event_metadata_json_round_trip() -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)

    audit_repo = SQLAlchemyAuditEventRepository(session)
    nested_metadata = {
        "username": "test",
        "source": "cli",
        "details": {"operation": "create-admin", "success": True},
    }

    event = audit_repo.create(
        event_type="user_registered",
        actor_id=None,
        metadata=nested_metadata,
    )

    assert event.metadata == nested_metadata

    row = session.query(AuthAuditEvent).filter_by(id=event.id).one()
    assert row.metadata_payload.startswith("{")
    assert "'username'" not in row.metadata_payload
    assert json.loads(row.metadata_payload) == nested_metadata

    listed = audit_repo.list(limit=1)[0]
    assert listed.metadata == nested_metadata

    session.close()


def test_audit_event_metadata_none_becomes_empty_object() -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)

    audit_repo = SQLAlchemyAuditEventRepository(session)
    event = audit_repo.create(event_type="login", actor_id=None, metadata=None)

    row = session.query(AuthAuditEvent).filter_by(id=event.id).one()
    assert row.metadata_payload == "{}"
    assert event.metadata == {}
    assert audit_repo.list(limit=1)[0].metadata == {}

    session.close()


def test_audit_event_legacy_malformed_payload_is_preserved() -> None:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)

    legacy_payload = "{'username': 'legacy_user'}"
    legacy_row = AuthAuditEvent(
        event_type="user_registered",
        subject_id=None,
        actor_id=None,
        metadata_payload=legacy_payload,
    )
    session.add(legacy_row)
    session.commit()

    audit_repo = SQLAlchemyAuditEventRepository(session)
    listed = audit_repo.list(limit=1)[0]

    assert listed.metadata == {"raw": legacy_payload}
    legacy_row_result = session.query(AuthAuditEvent).filter_by(id=legacy_row.id).one()
    assert legacy_row_result.metadata_payload == legacy_payload

    session.close()
