from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import BaseModel


class ScheduleRecord(BaseModel):
    __tablename__ = "schedules"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    executions: Mapped[list[ScheduleExecutionRecord]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ScheduleExecutionRecord(BaseModel):
    __tablename__ = "schedule_executions"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4, unique=True, nullable=False
    )
    schedule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    schedule: Mapped[ScheduleRecord] = relationship(back_populates="executions")
