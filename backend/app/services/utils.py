"""Common service utilities."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TypeVar

TValue = TypeVar("TValue")


@dataclass(frozen=True, slots=True)
class ServiceUtilities:
    """Namespace for reusable service helpers."""

    @staticmethod
    def require_value(value: TValue | None, message: str) -> TValue:
        """Ensure a value is present."""

        if value is None:
            raise ValueError(message)
        return value

    @staticmethod
    def chunked(values: Sequence[TValue], size: int) -> Iterator[tuple[TValue, ...]]:
        """Yield chunks from a sequence."""

        if size <= 0:
            raise ValueError("Chunk size must be positive.")

        for index in range(0, len(values), size):
            yield tuple(values[index : index + size])
