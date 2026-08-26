"""Add multi-transport discovery result state and summary fields.

Revision ID: 20260826_1200
Revises: 20260824_1500
Create Date: 2026-08-26 12:00:00.000000

This migration adds support for:
1. Discovery result state classification (unreachable, auth_failed, discovered, etc.)
2. Discovery summary aggregation fields for accurate reporting
3. Multi-transport attempt tracking enhancements

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = "20260826_1200"
down_revision = "20260824_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply multi-transport discovery schema changes."""

    # Add result_state column to discovery_device_results for accurate classification
    op.add_column(
        "discovery_device_results",
        sa.Column(
            "result_state",
            sa.String(32),
            nullable=True,
            index=True,
            comment="Discovery result classification: unreachable, reachable_no_management, authentication_failed, partial_discovery, discovered",
        ),
    )

    # Add columns for discovery summary aggregation
    op.add_column(
        "discovery_runs",
        sa.Column(
            "total_scanned",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Total number of addresses scanned",
        ),
    )

    op.add_column(
        "discovery_runs",
        sa.Column(
            "total_discovered",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Number of devices successfully discovered",
        ),
    )

    op.add_column(
        "discovery_runs",
        sa.Column(
            "total_unreachable",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Number of addresses that were unreachable",
        ),
    )

    op.add_column(
        "discovery_runs",
        sa.Column(
            "total_reachable_no_management",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Number of reachable hosts with no manageable service",
        ),
    )

    op.add_column(
        "discovery_runs",
        sa.Column(
            "total_authentication_failed",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Number of hosts where authentication failed",
        ),
    )

    op.add_column(
        "discovery_runs",
        sa.Column(
            "total_partial_discovery",
            sa.Integer,
            nullable=True,
            default=0,
            comment="Number of hosts with partial discovery only",
        ),
    )

    # Add allow_insecure_telnet flag to discovery targets
    op.add_column(
        "discovery_targets",
        sa.Column(
            "allow_insecure_telnet",
            sa.Boolean,
            nullable=False,
            default=False,
            comment="Whether to allow Telnet (insecure) for this target",
        ),
    )

    # Create indexes for efficient result state queries
    op.create_index(
        "idx_discovery_device_results_state",
        "discovery_device_results",
        ["result_state"],
    )

    op.create_index(
        "idx_discovery_device_results_job_state",
        "discovery_device_results",
        ["discovery_job_id", "result_state"],
    )


def downgrade() -> None:
    """Revert multi-transport discovery schema changes."""

    # Drop indexes
    op.drop_index("idx_discovery_device_results_job_state", "discovery_device_results")
    op.drop_index("idx_discovery_device_results_state", "discovery_device_results")

    # Drop columns from discovery_targets
    op.drop_column("discovery_targets", "allow_insecure_telnet")

    # Drop columns from discovery_runs
    op.drop_column("discovery_runs", "total_partial_discovery")
    op.drop_column("discovery_runs", "total_authentication_failed")
    op.drop_column("discovery_runs", "total_reachable_no_management")
    op.drop_column("discovery_runs", "total_unreachable")
    op.drop_column("discovery_runs", "total_discovered")
    op.drop_column("discovery_runs", "total_scanned")

    # Drop column from discovery_device_results
    op.drop_column("discovery_device_results", "result_state")