"""Add failure-message persistence for individual discovery transport attempts.

Revision ID: 20260826_1300
Revises: 20260826_1200
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_1300"
down_revision: str | None = "20260826_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discovery_transport_attempts",
        sa.Column("failure_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discovery_transport_attempts", "failure_message")