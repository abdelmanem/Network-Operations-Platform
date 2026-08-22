"""Align discovery_targets with the current ORM model.

Revision ID: 20260822_1300
Revises: 20260822_1200
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_1300"
down_revision: str | None = "20260822_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the missing discovery target columns expected by the ORM model."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("discovery_targets")}

    if "scope_type" not in existing_columns:
        op.add_column(
            "discovery_targets",
            sa.Column(
                "scope_type",
                sa.String(length=32),
                nullable=False,
                server_default="single_device",
            ),
        )
        op.execute(
            sa.text(
                "UPDATE discovery_targets SET scope_type = 'single_device' WHERE scope_type IS NULL OR scope_type = ''"
            )
        )
        op.execute(
            sa.text("ALTER TABLE discovery_targets ALTER COLUMN scope_type DROP DEFAULT")
        )

    if "scope_end" not in existing_columns:
        op.add_column(
            "discovery_targets",
            sa.Column("scope_end", sa.String(length=512), nullable=True),
        )

    if "scope_cidr" not in existing_columns:
        op.add_column(
            "discovery_targets",
            sa.Column("scope_cidr", sa.String(length=512), nullable=True),
        )

    if "credential_profile_id" not in existing_columns:
        op.add_column(
            "discovery_targets",
            sa.Column("credential_profile_id", sa.String(length=255), nullable=True),
        )

    if not inspector.get_indexes("discovery_targets") or not any(
        index["name"] == "ix_discovery_targets_scope_type"
        for index in inspector.get_indexes("discovery_targets")
    ):
        op.create_index(
            "ix_discovery_targets_scope_type",
            "discovery_targets",
            ["scope_type"],
        )


def downgrade() -> None:
    """Remove the extra discovery target columns added by this migration."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("discovery_targets")}

    if "ix_discovery_targets_scope_type" in {
        idx["name"] for idx in inspector.get_indexes("discovery_targets")
    }:
        op.drop_index("ix_discovery_targets_scope_type", table_name="discovery_targets")

    for column_name in ("credential_profile_id", "scope_cidr", "scope_end", "scope_type"):
        if column_name in existing_columns:
            op.drop_column("discovery_targets", column_name)
