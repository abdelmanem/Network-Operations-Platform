from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.models.base import BaseModel
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship


class _AuthMetadataMixin:
    """Provide a JSON-friendly metadata column without shadowing SQLAlchemy."""

    metadata_payload: Mapped[str] = mapped_column(String(2048), default="{}")


role_permissions = Table(
    "auth_role_permissions",
    BaseModel.metadata,
    Column(
        "role_id",
        Uuid(as_uuid=True),
        ForeignKey("auth_role.id"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Uuid(as_uuid=True),
        ForeignKey("auth_permission.id"),
        primary_key=True,
    ),
)

user_roles = Table(
    "auth_user_roles",
    BaseModel.metadata,
    Column(
        "user_id",
        Uuid(as_uuid=True),
        ForeignKey("auth_user.id"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Uuid(as_uuid=True),
        ForeignKey("auth_role.id"),
        primary_key=True,
    ),
)


class AuthPermission(BaseModel):
    __tablename__ = "auth_permission"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class AuthRole(BaseModel):
    __tablename__ = "auth_role"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    permissions: Mapped[list[AuthPermission]] = relationship(
        secondary=role_permissions,
        backref="roles",
    )


class AuthUser(BaseModel):
    __tablename__ = "auth_user"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    roles: Mapped[list[AuthRole]] = relationship(
        secondary=user_roles,
        backref="users",
    )


class AuthAuditEvent(BaseModel):
    __tablename__ = "auth_audit_event"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    metadata_payload: Mapped[str] = mapped_column(String(2048), default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
