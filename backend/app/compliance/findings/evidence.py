"""Evidence models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID, uuid4

from backend.app.compliance.domain.entities import ComplianceEntity


@dataclass(frozen=True, slots=True)
class Evidence(ComplianceEntity[UUID]):
    """Immutable evidence item."""

    source: str
    description: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reference: str | None = None
    details: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def create(
        cls,
        source: str,
        description: str,
        *,
        reference: str | None = None,
        details: Mapping[str, object] | None = None,
        captured_at: datetime | None = None,
    ) -> Evidence:
        """Create an evidence record with a generated identity."""

        return cls(
            id=uuid4(),
            source=source,
            description=description,
            reference=reference,
            details=(
                MappingProxyType({})
                if details is None
                else MappingProxyType(dict(details))
            ),
            captured_at=datetime.now(UTC) if captured_at is None else captured_at,
        )
