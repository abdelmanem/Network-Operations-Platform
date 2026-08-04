"""Base domain entities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BaseDomainEntity[TIdentity]:
    """Base class for mutable domain entities."""

    id: TIdentity

    def same_identity_as(self, other: object) -> bool:
        """Return whether another entity shares the same identity."""

        return isinstance(other, BaseDomainEntity) and self.id == other.id
