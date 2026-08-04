"""Immutable snapshot framework."""

from backend.app.snapshot.entities import (
    DeviceSnapshot,
    InterfaceSnapshot,
    InventorySnapshot,
    MACTableSnapshot,
    NeighborSnapshot,
    PowerSnapshot,
    VLANSnapshot,
)
from backend.app.snapshot.models import (
    DeviceSnapshotModel,
    InterfaceSnapshotModel,
    InventorySnapshotModel,
    MACTableSnapshotModel,
    NeighborSnapshotModel,
    PowerSnapshotModel,
    VLANSnapshotModel,
)
from backend.app.snapshot.repository import SnapshotRepository
from backend.app.snapshot.serializer import SnapshotSerializer
from backend.app.snapshot.validation import (
    SnapshotValidationError,
    validate_device_identity,
    validate_snapshot_integrity,
    validate_timestamp,
    validate_version,
)

__all__ = [
    "DeviceSnapshot",
    "DeviceSnapshotModel",
    "InventorySnapshot",
    "InventorySnapshotModel",
    "InterfaceSnapshot",
    "InterfaceSnapshotModel",
    "MACTableSnapshot",
    "MACTableSnapshotModel",
    "NeighborSnapshot",
    "NeighborSnapshotModel",
    "PowerSnapshot",
    "PowerSnapshotModel",
    "SnapshotRepository",
    "SnapshotSerializer",
    "SnapshotValidationError",
    "VLANSnapshot",
    "VLANSnapshotModel",
    "validate_device_identity",
    "validate_snapshot_integrity",
    "validate_timestamp",
    "validate_version",
]
