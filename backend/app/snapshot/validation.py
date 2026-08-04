"""Snapshot validation helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.app.core.exceptions import ApplicationError
from backend.app.snapshot.entities import SNAPSHOT_SCHEMA_VERSION
from backend.app.snapshot.models import (
    DeviceSnapshotModel,
    InterfaceSnapshotModel,
    InventorySnapshotModel,
    MACTableSnapshotModel,
    NeighborSnapshotModel,
    PowerSnapshotModel,
    VLANSnapshotModel,
)


class SnapshotValidationError(ApplicationError):
    """Raised when a snapshot is invalid."""


def validate_timestamp(timestamp: datetime, *, context: str) -> None:
    """Validate that a timestamp is not in the future."""

    if timestamp.tzinfo is None:
        raise SnapshotValidationError(f"{context} must be timezone-aware.")

    if timestamp > datetime.now(UTC) + timedelta(seconds=1):
        raise SnapshotValidationError(f"{context} cannot be in the future.")


def validate_device_identity(device_id: str, *, context: str) -> None:
    """Validate that a device identity is present."""

    if not device_id.strip():
        raise SnapshotValidationError(f"{context} must include a device identity.")


def validate_version(
    expected_version: str,
    actual_version: str,
    *,
    context: str,
) -> None:
    """Validate the snapshot schema version."""

    if actual_version != expected_version:
        raise SnapshotValidationError(
            f"{context} expected version {expected_version!r} "
            f"but received {actual_version!r}."
        )


def _validate_interface(snapshot: InterfaceSnapshotModel) -> None:
    validate_device_identity(snapshot.device_id, context="Interface snapshot")
    validate_timestamp(snapshot.captured_at, context="Interface snapshot timestamp")


def _validate_vlan(snapshot: VLANSnapshotModel) -> None:
    validate_timestamp(snapshot.captured_at, context="VLAN snapshot timestamp")


def _validate_mac_table(snapshot: MACTableSnapshotModel) -> None:
    validate_device_identity(snapshot.device_id, context="MAC table snapshot")
    validate_timestamp(snapshot.captured_at, context="MAC table snapshot timestamp")


def _validate_neighbor(snapshot: NeighborSnapshotModel) -> None:
    validate_device_identity(snapshot.local_device_id, context="Neighbor snapshot")
    validate_device_identity(snapshot.remote_device_id, context="Neighbor snapshot")
    validate_timestamp(snapshot.captured_at, context="Neighbor snapshot timestamp")


def _validate_power(snapshot: PowerSnapshotModel) -> None:
    validate_device_identity(snapshot.device_id, context="Power snapshot")
    validate_timestamp(snapshot.captured_at, context="Power snapshot timestamp")


def _validate_device(snapshot: DeviceSnapshotModel) -> None:
    validate_device_identity(snapshot.device_id, context="Device snapshot")
    validate_timestamp(snapshot.captured_at, context="Device snapshot timestamp")
    for interface in snapshot.interfaces:
        _validate_interface(interface)
    for vlan in snapshot.vlans:
        _validate_vlan(vlan)
    for mac_entry in snapshot.mac_table:
        _validate_mac_table(mac_entry)
    for neighbor in snapshot.neighbors:
        _validate_neighbor(neighbor)
    if snapshot.power is not None:
        _validate_power(snapshot.power)


def validate_snapshot_integrity(snapshot: InventorySnapshotModel) -> None:
    """Validate the integrity of a snapshot."""

    validate_version(
        SNAPSHOT_SCHEMA_VERSION,
        snapshot.version,
        context="Inventory snapshot",
    )
    validate_timestamp(snapshot.captured_at, context="Inventory snapshot timestamp")

    seen_device_ids: set[str] = set()
    for device in snapshot.devices:
        _validate_device(device)
        if device.device_id in seen_device_ids:
            raise SnapshotValidationError(
                "Inventory snapshot contains duplicate device identity: "
                f"{device.device_id}"
            )
        seen_device_ids.add(device.device_id)
