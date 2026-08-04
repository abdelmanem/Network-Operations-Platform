"""Domain layer interfaces."""

from __future__ import annotations

from typing import Protocol


class DomainEntity[TIdentity](Protocol):
    """Protocol for domain entities."""

    id: TIdentity


class DomainValueObject(Protocol):
    """Protocol for domain value objects."""

    components: tuple[object, ...]
