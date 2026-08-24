"""Add durable cooperative cancellation metadata to discovery jobs.

Revision ID: 20260824_1200
Revises: 20260822_1300
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_1200"
down_revision: str | None = "20260822_1300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discovery_jobs",
        sa.Column(
            "cancellation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "discovery_jobs",
        sa.Column("cancellation_requested_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "discovery_jobs",
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discovery_jobs", "cancellation_reason")
    op.drop_column("discovery_jobs", "cancellation_requested_by")
    op.drop_column("discovery_jobs", "cancellation_requested_at")
