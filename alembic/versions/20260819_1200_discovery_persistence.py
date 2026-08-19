"""Create M31 discovery persistence tables.

Revision ID: 20260819_1200
Revises: 20260817_1200
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_1200"
down_revision: str | None = "20260817_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVE_STATES = "state IN ('queued', 'running')"


def upgrade() -> None:
    """Create tenant-scoped discovery persistence tables and indexes."""

    op.add_column(
        "discovery_runs",
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_discovery_runs_tenant_id", "discovery_runs", ["tenant_id"])

    op.create_table(
        "discovery_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=512), nullable=False),
        sa.Column("platform_hint", sa.String(length=128), nullable=True),
        sa.Column("preferred_transport", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("credential_reference", sa.String(length=255), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "identifier",
            name="uq_discovery_targets_tenant_identifier",
        ),
    )
    op.create_index(
        "ix_discovery_targets_tenant_id", "discovery_targets", ["tenant_id"]
    )

    op.create_table(
        "discovery_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_job_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_capabilities", sa.JSON(), nullable=False),
        sa.Column("selected_transport", sa.String(length=64), nullable=True),
        sa.Column("selected_platform", sa.String(length=128), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["target_id"], ["discovery_targets.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"]),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', "
            "'timed_out', 'cancelled')",
            name="ck_discovery_jobs_state",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_jobs_tenant_id", "discovery_jobs", ["tenant_id"])
    op.create_index("ix_discovery_jobs_target_id", "discovery_jobs", ["target_id"])
    op.create_index("ix_discovery_jobs_run_id", "discovery_jobs", ["run_id"])
    op.create_index("ix_discovery_jobs_state", "discovery_jobs", ["state"])
    op.create_index(
        "ix_discovery_jobs_tenant_created_at",
        "discovery_jobs",
        ["tenant_id", "requested_at"],
    )
    op.create_index(
        "ix_discovery_jobs_target_created_at",
        "discovery_jobs",
        ["target_id", "requested_at"],
    )
    op.create_index(
        "uq_discovery_jobs_active_tenant_target",
        "discovery_jobs",
        ["tenant_id", "target_id"],
        unique=True,
        postgresql_where=sa.text(_ACTIVE_STATES),
        sqlite_where=sa.text(_ACTIVE_STATES),
    )

    op.create_table(
        "discovery_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("collector", sa.String(length=255), nullable=False),
        sa.Column("collector_version", sa.String(length=64), nullable=True),
        sa.Column("command_or_probe", sa.String(length=512), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("normalization_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["discovery_jobs.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["discovery_targets.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_discovery_evidence_tenant_id", "discovery_evidence", ["tenant_id"]
    )
    op.create_index("ix_discovery_evidence_job_id", "discovery_evidence", ["job_id"])
    op.create_index(
        "ix_discovery_evidence_target_id", "discovery_evidence", ["target_id"]
    )
    op.create_index("ix_discovery_evidence_run_id", "discovery_evidence", ["run_id"])
    op.create_index(
        "ix_discovery_evidence_target_observed_at",
        "discovery_evidence",
        ["target_id", "observed_at"],
    )
    op.create_index(
        "ix_discovery_evidence_payload_hash",
        "discovery_evidence",
        ["payload_hash"],
    )


def downgrade() -> None:
    """Drop M31 discovery persistence tables and indexes."""

    op.drop_index("ix_discovery_evidence_payload_hash", table_name="discovery_evidence")
    op.drop_index(
        "ix_discovery_evidence_target_observed_at", table_name="discovery_evidence"
    )
    op.drop_index("ix_discovery_evidence_run_id", table_name="discovery_evidence")
    op.drop_index("ix_discovery_evidence_target_id", table_name="discovery_evidence")
    op.drop_index("ix_discovery_evidence_job_id", table_name="discovery_evidence")
    op.drop_index("ix_discovery_evidence_tenant_id", table_name="discovery_evidence")
    op.drop_table("discovery_evidence")
    op.drop_index("uq_discovery_jobs_active_tenant_target", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_target_created_at", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_tenant_created_at", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_state", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_run_id", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_target_id", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_tenant_id", table_name="discovery_jobs")
    op.drop_table("discovery_jobs")
    op.drop_index("ix_discovery_targets_tenant_id", table_name="discovery_targets")
    op.drop_table("discovery_targets")
    op.drop_index("ix_discovery_runs_tenant_id", table_name="discovery_runs")
    op.drop_column("discovery_runs", "tenant_id")
