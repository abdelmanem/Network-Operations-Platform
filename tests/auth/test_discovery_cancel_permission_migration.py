"""Isolated coverage for the discovery cancellation RBAC data migration."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend.app.auth.infrastructure.models import AuthPermission, AuthRole, AuthUser
from backend.app.models.base import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

_migration_path = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260824_1300_provision_discovery_job_cancel_permission.py"
)
_migration_spec = spec_from_file_location(
    "discovery_cancel_permission_migration", _migration_path
)
assert _migration_spec is not None and _migration_spec.loader is not None
migration = module_from_spec(_migration_spec)
_migration_spec.loader.exec_module(migration)


def test_provisions_cancel_permission_for_existing_admin_idempotently() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    try:
        read_permission = AuthPermission(name="discovery:job:read")
        admin = AuthRole(name="admin", permissions=[read_permission])
        observer = AuthRole(name="observer", permissions=[read_permission])
        user = AuthUser(
            username="existing-admin",
            email="existing-admin@example.com",
            password_hash="not-used",
            roles=[admin],
        )
        session.add_all([admin, observer, user])
        session.commit()
        user_id = user.id

        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.upgrade()
                migration.upgrade()

        session.expire_all()
        permission = session.scalar(
            select(AuthPermission).where(AuthPermission.name == "discovery:job:cancel")
        )
        refreshed_admin = session.scalar(
            select(AuthRole).where(AuthRole.name == "admin")
        )
        refreshed_observer = session.scalar(
            select(AuthRole).where(AuthRole.name == "observer")
        )

        assert permission is not None
        assert refreshed_admin is not None
        assert {item.name for item in refreshed_admin.permissions} == {
            "discovery:job:read",
            "discovery:job:cancel",
        }
        assert refreshed_observer is not None
        assert {item.name for item in refreshed_observer.permissions} == {
            "discovery:job:read"
        }
        assert session.get(AuthUser, user_id) is not None
        assert (
            session.scalar(
                select(AuthPermission).where(
                    AuthPermission.name == "discovery:job:cancel"
                )
            )
            is not None
        )
        assert (
            len(
                session.scalars(
                    select(AuthPermission).where(
                        AuthPermission.name == "discovery:job:cancel"
                    )
                ).all()
            )
            == 1
        )
    finally:
        session.close()


def test_existing_permission_is_linked_without_altering_other_roles() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    try:
        cancel_permission = AuthPermission(name="discovery:job:cancel")
        admin = AuthRole(name="admin")
        operator = AuthRole(name="operator", permissions=[cancel_permission])
        session.add_all([cancel_permission, admin, operator])
        session.commit()

        with engine.begin() as connection:
            migration.provision_discovery_job_cancel_permission(connection)

        session.expire_all()
        refreshed_admin = session.scalar(
            select(AuthRole).where(AuthRole.name == "admin")
        )
        refreshed_operator = session.scalar(
            select(AuthRole).where(AuthRole.name == "operator")
        )
        assert refreshed_admin is not None
        assert {item.name for item in refreshed_admin.permissions} == {
            "discovery:job:cancel"
        }
        assert refreshed_operator is not None
        assert {item.name for item in refreshed_operator.permissions} == {
            "discovery:job:cancel"
        }
    finally:
        session.close()
