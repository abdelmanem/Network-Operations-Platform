"""Immutable snapshot entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

SNAPSHOT_SCHEMA_VERSION = "1.0.0"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class InterfaceSnapshot:
    """Immutable interface snapshot entity."""

    device_id: str
    name: str
    captured_at: datetime = field(default_factory=_utc_now)
    version: str = SNAPSHOT_SCHEMA_VERSION
    admin_status: str | None = None
    oper_status: str | None = None
    description: str | None = None
    mac_address: str | None = None
    speed_mbps: int | None = None


@dataclass(frozen=True, slots=True)
class VLANSnapshot:
    """Immutable VLAN snapshot entity."""

    vlan_id: int
    name: str
    captured_at: datetime = field(default_factory=_utc_now)
    version: str = SNAPSHOT_SCHEMA_VERSION
    device_id: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class MACTableSnapshot:
    """Immutable MAC table snapshot entity."""

    mac_address: str
    device_id: str
    interface_name: str
    captured_at: datetime = field(default_factory=_utc_now)
    version: str = SNAPSHOT_SCHEMA_VERSION
    vlan_id: int | None = None
    last_seen: datetime | None = None


@dataclass(frozen=True, slots=True)
class NeighborSnapshot:
    """Immutable neighbor snapshot entity."""

    local_device_id: str
    local_interface: str
    remote_device_id: str
    remote_interface: str | None = None
    protocol: str | None = None
    captured_at: datetime = field(default_factory=_utc_now)
    version: str = SNAPSHOT_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class PowerSnapshot:
    """Immutable power snapshot entity."""

    device_id: str
    source: str
    captured_at: datetime = field(default_factory=_utc_now)
    version: str = SNAPSHOT_SCHEMA_VERSION
    status: str | None = None
    available_watts: float | None = None
    consumed_watts: float | None = None
    poe_enabled: bool | None = None


@dataclass(frozen=True, slots=True)
class DeviceSnapshot:
    """Immutable device snapshot entity."""

    device_id: str
    name: str
    captured_at: datetime = field(default_factory=_utc_now)
    version: str = SNAPSHOT_SCHEMA_VERSION
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    platform: str | None = None
    interfaces: tuple[InterfaceSnapshot, ...] = field(default_factory=tuple)
    vlans: tuple[VLANSnapshot, ...] = field(default_factory=tuple)
    mac_table: tuple[MACTableSnapshot, ...] = field(default_factory=tuple)
    neighbors: tuple[NeighborSnapshot, ...] = field(default_factory=tuple)
    power: PowerSnapshot | None = None


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    """Immutable inventory snapshot entity."""

    devices: tuple[DeviceSnapshot, ...] = field(default_factory=tuple)
    snapshot_id: UUID = field(default_factory=uuid4)
    captured_at: datetime = field(default_factory=_utc_now)
    version: str = SNAPSHOT_SCHEMA_VERSION
    source: str | None = None

    @classmethod
    def empty(cls) -> InventorySnapshot:
        """Return an empty inventory snapshot."""

        return cls()

    @classmethod
    def merge(cls, *snapshots: InventorySnapshot) -> InventorySnapshot:
        """Merge multiple inventory snapshots into a single snapshot."""

        if not snapshots:
            return cls.empty()

        merged_devices: dict[str, DeviceSnapshot] = {}
        latest_captured_at = snapshots[0].captured_at
        latest_version = snapshots[0].version
        latest_source = snapshots[0].source
        for snapshot in snapshots:
            if snapshot.captured_at > latest_captured_at:
                latest_captured_at = snapshot.captured_at
            latest_version = snapshot.version
            if snapshot.source is not None:
                latest_source = snapshot.source
            for device in snapshot.devices:
                merged_devices[device.device_id] = device

        return cls(
            devices=tuple(merged_devices.values()),
            captured_at=latest_captured_at,
            version=latest_version,
            source=latest_source,
        )
