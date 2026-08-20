"""Add per-device discovery results and transport attempts.

Revision ID: 20260820_0900
Revises: 20260819_1300
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0900"
down_revision: str | None = "20260819_1300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discovery_jobs",
        sa.Column("parent_job_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_discovery_jobs_parent_job_id",
        "discovery_jobs",
        "discovery_jobs",
        ["parent_job_id"],
        ["id"],
    )
    op.create_index(
        "ix_discovery_jobs_parent_job_id", "discovery_jobs", ["parent_job_id"]
    )

    op.create_table(
        "discovery_device_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("discovery_job_id", sa.Uuid(), nullable=False),
        sa.Column("child_job_id", sa.Uuid(), nullable=False),
        sa.Column("address", sa.String(length=512), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("vendor", sa.String(length=128), nullable=True),
        sa.Column("platform", sa.String(length=128), nullable=True),
        sa.Column("state", sa.String(length=48), nullable=False),
        sa.Column("selected_transport", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["discovery_job_id"], ["discovery_jobs.id"]),
        sa.ForeignKeyConstraint(["child_job_id"], ["discovery_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_job_id"),
    )
    op.create_index(
        "ix_discovery_device_results_tenant_id",
        "discovery_device_results",
        ["tenant_id"],
    )
    op.create_index(
        "ix_discovery_device_results_discovery_job_id",
        "discovery_device_results",
        ["discovery_job_id"],
    )
    op.create_index(
        "ix_discovery_device_results_state", "discovery_device_results", ["state"]
    )

    op.create_table(
        "discovery_transport_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("device_result_id", sa.Uuid(), nullable=False),
        sa.Column("transport", sa.String(length=64), nullable=False),
        sa.Column("attempt_order", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=48), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_result_id"], ["discovery_device_results.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_discovery_transport_attempts_tenant_id",
        "discovery_transport_attempts",
        ["tenant_id"],
    )
    op.create_index(
        "ix_discovery_transport_attempts_device_result_id",
        "discovery_transport_attempts",
        ["device_result_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_discovery_transport_attempts_device_result_id",
        table_name="discovery_transport_attempts",
    )
    op.drop_index(
        "ix_discovery_transport_attempts_tenant_id",
        table_name="discovery_transport_attempts",
    )
    op.drop_table("discovery_transport_attempts")
    op.drop_index(
        "ix_discovery_device_results_state", table_name="discovery_device_results"
    )
    op.drop_index(
        "ix_discovery_device_results_discovery_job_id",
        table_name="discovery_device_results",
    )
    op.drop_index(
        "ix_discovery_device_results_tenant_id", table_name="discovery_device_results"
    )
    op.drop_table("discovery_device_results")
    op.drop_index("ix_discovery_jobs_parent_job_id", table_name="discovery_jobs")
    op.drop_constraint(
        "fk_discovery_jobs_parent_job_id", "discovery_jobs", type_="foreignkey"
    )
    op.drop_column("discovery_jobs", "parent_job_id")
