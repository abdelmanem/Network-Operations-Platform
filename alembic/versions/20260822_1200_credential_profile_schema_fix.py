"""Align credential_profiles with the current ORM model.

Revision ID: 20260822_1200
Revises: 20260820_1010
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_1200"
down_revision: str | None = "20260820_1010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("credential_profiles")}

    if "vendor" not in existing_columns:
        op.add_column(
            "credential_profiles",
            sa.Column("vendor", sa.String(length=128), nullable=True),
        )

    if "platform" not in existing_columns:
        op.add_column(
            "credential_profiles",
            sa.Column("platform", sa.String(length=128), nullable=True),
        )

    if "credential_type" not in existing_columns:
        op.add_column(
            "credential_profiles",
            sa.Column("credential_type", sa.String(length=64), nullable=True),
        )

    if "username" not in existing_columns:
        op.add_column(
            "credential_profiles",
            sa.Column("username", sa.String(length=255), nullable=True),
        )

    if "secret_status" not in existing_columns:
        op.add_column(
            "credential_profiles",
            sa.Column(
                "secret_status",
                sa.String(length=32),
                nullable=False,
                server_default="configured",
            ),
        )

    op.execute(
        sa.text(
            "UPDATE credential_profiles SET secret_status = 'configured' WHERE secret_status IS NULL"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE credential_profiles ALTER COLUMN secret_status DROP DEFAULT"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("credential_profiles")}

    for column_name in ("secret_status", "username", "credential_type", "platform", "vendor"):
        if column_name in existing_columns:
            op.drop_column("credential_profiles", column_name)
