"""Add timestamps and correlation to transport attempts.

Revision ID: 20260820_1000
Revises: 20260820_0900
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_1000"
down_revision: str | None = "20260820_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discovery_transport_attempts",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "discovery_transport_attempts",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "discovery_transport_attempts",
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE discovery_transport_attempts "
            "SET started_at = attempted_at WHERE started_at IS NULL"
        )
    )
    op.alter_column("discovery_transport_attempts", "started_at", nullable=False)
    op.drop_column("discovery_transport_attempts", "attempted_at")


def downgrade() -> None:
    op.add_column(
        "discovery_transport_attempts",
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE discovery_transport_attempts "
            "SET attempted_at = started_at WHERE attempted_at IS NULL"
        )
    )
    op.alter_column("discovery_transport_attempts", "attempted_at", nullable=False)
    op.drop_column("discovery_transport_attempts", "correlation_id")
    op.drop_column("discovery_transport_attempts", "completed_at")
    op.drop_column("discovery_transport_attempts", "started_at")
