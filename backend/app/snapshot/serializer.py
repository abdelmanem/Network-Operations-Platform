"""Snapshot serialization helpers."""

from __future__ import annotations

from backend.app.snapshot.models import InventorySnapshotModel


class SnapshotSerializer:
    """Serialize and deserialize snapshot models."""

    def serialize(self, snapshot: InventorySnapshotModel) -> bytes:
        """Serialize a snapshot model to JSON bytes."""

        return snapshot.model_dump_json().encode("utf-8")

    def deserialize(self, payload: bytes) -> InventorySnapshotModel:
        """Deserialize JSON bytes into a snapshot model."""

        return InventorySnapshotModel.model_validate_json(payload)
