from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0900"
down_revision: str | None = "20260806_1300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("resource_type", sa.String(length=255), nullable=True),
        sa.Column("resource_id", sa.String(length=512), nullable=True),
        sa.Column("outcome", sa.String(length=255), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("metadata_payload", sa.String(length=4096), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_record_event_type"), "audit_record", ["event_type"])
    op.create_index(op.f("ix_audit_record_created_at"), "audit_record", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_record_created_at"), table_name="audit_record")
    op.drop_index(op.f("ix_audit_record_event_type"), table_name="audit_record")
    op.drop_table("audit_record")
