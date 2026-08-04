"""Base compliance value objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ComplianceValueObject(ABC):
    """Base class for immutable compliance value objects."""

    @property
    @abstractmethod
    def components(self) -> tuple[Any, ...]:
        """Return the ordered components that define equality."""

    def __iter__(self) -> Iterator[Any]:
        return iter(self.components)

    def __hash__(self) -> int:
        return hash(self.components)
