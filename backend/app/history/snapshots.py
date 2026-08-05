"""Snapshot history queries."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.app.persistence.models import SnapshotRecord, SnapshotSource
from backend.app.persistence.repositories import SnapshotRepository


@dataclass(slots=True)
class SnapshotHistory:
    """Read immutable snapshot history."""

    repository: SnapshotRepository

    def get(self, identity: UUID) -> SnapshotRecord | None:
        """Return one snapshot."""

        return self.repository.get(identity)

    def list(self) -> tuple[SnapshotRecord, ...]:
        """Return all snapshots."""

        return self.repository.list()

    def list_live(self) -> tuple[SnapshotRecord, ...]:
        """Return all live snapshots."""

        return self.repository.list_by_source(SnapshotSource.LIVE)

    def list_netbox(self) -> tuple[SnapshotRecord, ...]:
        """Return all NetBox snapshots."""

        return self.repository.list_by_source(SnapshotSource.NETBOX)
