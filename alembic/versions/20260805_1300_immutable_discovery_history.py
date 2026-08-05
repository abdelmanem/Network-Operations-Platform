"""Create immutable discovery history tables.

Revision ID: 20260805_1300
Revises:
Create Date: 2026-08-05 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_1300"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable history tables."""

    op.create_table(
        "discovery_runs",
        sa.Column("target_identifier", sa.String(length=255), nullable=False),
        sa.Column("target_address", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_table(
        "snapshots",
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("discovery_run_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_table(
        "comparison_results",
        sa.Column("expected_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("observed_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("compared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["expected_snapshot_id"], ["snapshots.id"]),
        sa.ForeignKeyConstraint(["observed_snapshot_id"], ["snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_comparison_results_expected_snapshot_id",
        "comparison_results",
        ["expected_snapshot_id"],
    )
    op.create_index(
        "ix_comparison_results_observed_snapshot_id",
        "comparison_results",
        ["observed_snapshot_id"],
    )
    op.create_table(
        "snapshot_devices",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("serial_number", sa.String(length=255), nullable=True),
        sa.Column("product_id", sa.String(length=255), nullable=True),
        sa.Column("management_ip", sa.String(length=128), nullable=True),
        sa.Column("platform", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_snapshot_devices_snapshot_id",
        "snapshot_devices",
        ["snapshot_id"],
    )
    op.create_index("ix_snapshot_devices_device_id", "snapshot_devices", ["device_id"])
    op.create_index("ix_snapshot_devices_name", "snapshot_devices", ["name"])
    op.create_table(
        "findings",
        sa.Column("comparison_result_id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expected_state", sa.JSON(), nullable=False),
        sa.Column("observed_state", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_result_id"], ["comparison_results.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_findings_comparison_result_id",
        "findings",
        ["comparison_result_id"],
    )
    op.create_table(
        "snapshot_interfaces",
        sa.Column("snapshot_device_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("admin_status", sa.String(length=64), nullable=True),
        sa.Column("oper_status", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mac_address", sa.String(length=64), nullable=True),
        sa.Column("speed_mbps", sa.Integer(), nullable=True),
        sa.Column("poe_status", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_device_id"], ["snapshot_devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_snapshot_interfaces_snapshot_device_id",
        "snapshot_interfaces",
        ["snapshot_device_id"],
    )
    op.create_table(
        "snapshot_neighbors",
        sa.Column("snapshot_device_id", sa.Uuid(), nullable=False),
        sa.Column("local_interface", sa.String(length=255), nullable=False),
        sa.Column("remote_device_id", sa.String(length=255), nullable=False),
        sa.Column("remote_interface", sa.String(length=255), nullable=True),
        sa.Column("protocol", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_device_id"], ["snapshot_devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_snapshot_neighbors_snapshot_device_id",
        "snapshot_neighbors",
        ["snapshot_device_id"],
    )
    op.create_table(
        "snapshot_vlans",
        sa.Column("snapshot_device_id", sa.Uuid(), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_device_id"], ["snapshot_devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_snapshot_vlans_snapshot_device_id",
        "snapshot_vlans",
        ["snapshot_device_id"],
    )
    op.create_index("ix_snapshot_vlans_vlan_id", "snapshot_vlans", ["vlan_id"])
    op.create_table(
        "evidence",
        sa.Column("finding_record_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(length=512), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["finding_record_id"], ["findings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )
    op.create_index("ix_evidence_finding_record_id", "evidence", ["finding_record_id"])


def downgrade() -> None:
    """Drop immutable history tables."""

    op.drop_index("ix_evidence_finding_record_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_snapshot_vlans_vlan_id", table_name="snapshot_vlans")
    op.drop_index("ix_snapshot_vlans_snapshot_device_id", table_name="snapshot_vlans")
    op.drop_table("snapshot_vlans")
    op.drop_index(
        "ix_snapshot_neighbors_snapshot_device_id",
        table_name="snapshot_neighbors",
    )
    op.drop_table("snapshot_neighbors")
    op.drop_index(
        "ix_snapshot_interfaces_snapshot_device_id",
        table_name="snapshot_interfaces",
    )
    op.drop_table("snapshot_interfaces")
    op.drop_index("ix_findings_comparison_result_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_snapshot_devices_name", table_name="snapshot_devices")
    op.drop_index("ix_snapshot_devices_device_id", table_name="snapshot_devices")
    op.drop_index("ix_snapshot_devices_snapshot_id", table_name="snapshot_devices")
    op.drop_table("snapshot_devices")
    op.drop_index(
        "ix_comparison_results_observed_snapshot_id",
        table_name="comparison_results",
    )
    op.drop_index(
        "ix_comparison_results_expected_snapshot_id",
        table_name="comparison_results",
    )
    op.drop_table("comparison_results")
    op.drop_table("snapshots")
    op.drop_table("discovery_runs")
