"""Snapshot repository interfaces."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.snapshot.models import InventorySnapshotModel


class SnapshotRepository(Protocol):
    """Protocol for immutable snapshot storage."""

    async def save(self, snapshot: InventorySnapshotModel) -> None:
        """Persist a snapshot."""

    async def get(self, snapshot_id: UUID) -> InventorySnapshotModel | None:
        """Return a snapshot by identifier."""

    async def list(self) -> tuple[InventorySnapshotModel, ...]:
        """Return all stored snapshots."""

    async def delete(self, snapshot_id: UUID) -> None:
        """Remove a snapshot."""

    async def clear(self) -> None:
        """Remove all snapshots."""
