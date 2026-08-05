"""Difference models for inventory comparison."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID, uuid4


class DifferenceType(StrEnum):
    """Supported inventory difference types."""

    MISSING = "missing"
    UNEXPECTED = "unexpected"
    MODIFIED = "modified"
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Difference:
    """Immutable inventory difference."""

    difference_type: DifferenceType
    subject_type: str
    subject_id: str
    field_name: str | None = None
    expected: object | None = None
    observed: object | None = None
    description: str | None = None
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    id: UUID = field(default_factory=uuid4)
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        difference_type: DifferenceType,
        subject_type: str,
        subject_id: str,
        *,
        field_name: str | None = None,
        expected: object | None = None,
        observed: object | None = None,
        description: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Difference:
        """Create a difference with immutable metadata."""

        return cls(
            difference_type=difference_type,
            subject_type=subject_type,
            subject_id=subject_id,
            field_name=field_name,
            expected=expected,
            observed=observed,
            description=description,
            metadata=MappingProxyType({} if metadata is None else dict(metadata)),
        )

    @property
    def key(self) -> str:
        """Return a stable difference key for registries and tests."""

        field = "" if self.field_name is None else self.field_name
        return (
            f"{self.difference_type.value}:{self.subject_type}:"
            f"{self.subject_id}:{field}"
        )
