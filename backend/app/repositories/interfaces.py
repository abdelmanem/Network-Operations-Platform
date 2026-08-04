"""Repository interfaces."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class SupportsUUIDIdentity(Protocol):
    """Protocol for models with UUID identity."""

    id: UUID


class GenericRepository[TModel](Protocol):
    """Generic repository contract."""

    def add(self, item: TModel) -> TModel:
        """Add an item to the repository."""

    def get(self, identity: UUID) -> TModel | None:
        """Return an item by identifier."""

    def list(self) -> tuple[TModel, ...]:
        """Return all items."""

    def remove(self, item: TModel) -> None:
        """Remove an item from the repository."""
