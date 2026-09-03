"""add_total_unverified

Revision ID: 5689b3c308fa
Revises: 20260826_1300
Create Date: 2026-09-02 16:46:00.643244
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5689b3c308fa'
down_revision = '20260826_1300'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discovery_runs", sa.Column("total_unverified", sa.Integer(), nullable=True, server_default="0"))

def downgrade() -> None:
    op.drop_column("discovery_runs", "total_unverified")

