from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_1000"
down_revision: str | None = "20260809_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "auth_audit_event",
        "metadata",
        new_column_name="metadata_payload",
        existing_type=sa.String(length=2048),
        existing_nullable=True,
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported for auth_audit_event metadata reconciliation."
    )
