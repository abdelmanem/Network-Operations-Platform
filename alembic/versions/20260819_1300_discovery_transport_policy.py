"""Add multi-transport discovery target policy fields.

Revision ID: 20260819_1300
Revises: 20260819_1200
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_1300"
down_revision: str | None = "20260819_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add vendor, hostname, fallback policy, and credential reference fields."""

    op.add_column(
        "discovery_targets",
        sa.Column("vendor", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "discovery_targets",
        sa.Column("hostname", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "discovery_targets",
        sa.Column(
            "scope_type",
            sa.String(length=32),
            nullable=False,
            server_default="single_device",
        ),
    )
    op.add_column(
        "discovery_targets",
        sa.Column("scope_end", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "discovery_targets",
        sa.Column("scope_cidr", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "discovery_targets",
        sa.Column("credential_profile_id", sa.String(length=255), nullable=True),
    )
    op.alter_column("discovery_targets", "scope_type", server_default=None)
    op.add_column(
        "discovery_targets",
        sa.Column(
            "credential_references", sa.JSON(), nullable=False, server_default="{}"
        ),
    )
    op.add_column(
        "discovery_targets",
        sa.Column(
            "allowed_fallback_transports",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )
    op.alter_column("discovery_targets", "credential_references", server_default=None)
    op.alter_column(
        "discovery_targets", "allowed_fallback_transports", server_default=None
    )


def downgrade() -> None:
    """Remove multi-transport discovery target policy fields."""

    op.drop_column("discovery_targets", "allowed_fallback_transports")
    op.drop_column("discovery_targets", "credential_references")
    op.drop_column("discovery_targets", "hostname")
    op.drop_column("discovery_targets", "vendor")
    op.drop_column("discovery_targets", "credential_profile_id")
    op.drop_column("discovery_targets", "scope_cidr")
    op.drop_column("discovery_targets", "scope_end")
    op.drop_column("discovery_targets", "scope_type")
