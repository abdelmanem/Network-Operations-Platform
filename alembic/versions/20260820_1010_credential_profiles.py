"""Add secret-free credential profile metadata.

Revision ID: 20260820_1010
Revises: 20260820_1000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_1010"
down_revision: str | None = "20260820_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credential_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("transport_types", sa.JSON(), nullable=False),
        sa.Column("provider_reference", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credential_profiles_tenant_id", "credential_profiles", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_credential_profiles_tenant_id", table_name="credential_profiles")
    op.drop_table("credential_profiles")
