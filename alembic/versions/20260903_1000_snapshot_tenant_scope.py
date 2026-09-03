"""Add tenant ownership to immutable snapshots.

Revision ID: 20260903_1000
Revises: 5689b3c308fa
Create Date: 2026-09-03 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260903_1000"
down_revision = "5689b3c308fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "snapshots",
        sa.Column(
            "tenant_id",
            sa.String(255),
            nullable=False,
            server_default="default",
        ),
    )
    op.create_index("ix_snapshots_tenant_id", "snapshots", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_snapshots_tenant_id", table_name="snapshots")
    op.drop_column("snapshots", "tenant_id")
