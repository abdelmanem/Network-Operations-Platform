"""Add durable worker lease metadata to discovery jobs.

Revision ID: 20260824_1400
Revises: 20260824_1300
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_1400"
down_revision: str | None = "20260824_1300"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.add_column(
        "discovery_jobs",
        sa.Column("execution_owner", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "discovery_jobs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "discovery_jobs",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_discovery_jobs_execution_lease",
        "discovery_jobs",
        ["state", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_jobs_execution_lease", table_name="discovery_jobs")
    op.drop_column("discovery_jobs", "last_heartbeat_at")
    op.drop_column("discovery_jobs", "lease_expires_at")
    op.drop_column("discovery_jobs", "execution_owner")
