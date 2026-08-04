"""Base compliance entities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComplianceEntity[TIdentity]:
    """Base class for immutable compliance entities."""

    id: TIdentity

    def same_identity_as(self, other: object) -> bool:
        """Return whether another entity shares the same identity."""

        return isinstance(other, ComplianceEntity) and self.id == other.id
