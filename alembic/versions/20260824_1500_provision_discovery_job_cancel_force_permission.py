"""Provision the force discovery-job cancellation permission for admins.

Revision ID: 20260824_1500
Revises: 20260824_1400
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_1500"
down_revision: str | None = "20260824_1400"
branch_labels: None = None
depends_on: None = None

_ADMIN_ROLE = "admin"
_PERMISSION = "discovery:job:cancel:force"


def _auth_tables() -> tuple[sa.Table, sa.Table, sa.Table]:
    metadata = sa.MetaData()
    permissions = sa.Table(
        "auth_permission",
        metadata,
        sa.Column("id", sa.Uuid(as_uuid=True)),
        sa.Column("name", sa.String(255)),
        sa.Column("description", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    roles = sa.Table(
        "auth_role",
        metadata,
        sa.Column("id", sa.Uuid(as_uuid=True)),
        sa.Column("name", sa.String(255)),
    )
    role_permissions = sa.Table(
        "auth_role_permissions",
        metadata,
        sa.Column("role_id", sa.Uuid(as_uuid=True)),
        sa.Column("permission_id", sa.Uuid(as_uuid=True)),
    )
    return permissions, roles, role_permissions


def provision_discovery_job_cancel_force_permission(connection: sa.Connection) -> None:
    """Idempotently provision only the global admin force cancellation permission."""

    permissions, roles, role_permissions = _auth_tables()
    permission_id = connection.scalar(
        sa.select(permissions.c.id).where(permissions.c.name == _PERMISSION)
    )
    if permission_id is None:
        permission_id = uuid4()
        now = datetime.now(UTC)
        connection.execute(
            permissions.insert().values(
                id=permission_id,
                name=_PERMISSION,
                description="Administrative access: discovery:job:cancel:force",
                created_at=now,
                updated_at=now,
            )
        )

    admin_role_id = connection.scalar(
        sa.select(roles.c.id).where(roles.c.name == _ADMIN_ROLE)
    )
    if admin_role_id is None:
        return

    link_exists = connection.scalar(
        sa.select(role_permissions.c.role_id).where(
            role_permissions.c.role_id == admin_role_id,
            role_permissions.c.permission_id == permission_id,
        )
    )
    if link_exists is None:
        connection.execute(
            role_permissions.insert().values(
                role_id=admin_role_id,
                permission_id=permission_id,
            )
        )


def upgrade() -> None:
    provision_discovery_job_cancel_force_permission(op.get_bind())


def downgrade() -> None:
    """Intentionally retain provisioned RBAC data to avoid unsafe revocation."""
