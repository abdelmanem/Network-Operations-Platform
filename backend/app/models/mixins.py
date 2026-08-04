"""Common ORM mixins."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TableNameMixin:
    """Provide automatic table name generation."""

    @declared_attr.directive
    def __tablename__(self) -> str:
        model_class = cast(type[Any], self)
        return model_class.__name__.lower()


class UUIDPrimaryKeyMixin:
    """Provide a UUID primary key column."""

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        unique=True,
        nullable=False,
    )


class TimestampMixin:
    """Provide created and updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=func.now(),
        nullable=False,
    )


class RepresentationMixin:
    """Provide a stable dictionary representation."""

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the ORM object."""

        return {
            key: value
            for key, value in vars(self).items()
            if not key.startswith("_sa_")
        }
