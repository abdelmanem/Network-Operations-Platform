"""Pydantic snapshot models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.snapshot.entities import SNAPSHOT_SCHEMA_VERSION


class SnapshotModel(BaseModel):
    """Base class for immutable snapshot models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class InterfaceSnapshotModel(SnapshotModel):
    """Immutable interface snapshot model."""

    device_id: str
    name: str
    captured_at: datetime
    version: str = SNAPSHOT_SCHEMA_VERSION
    admin_status: str | None = None
    oper_status: str | None = None
    description: str | None = None
    mac_address: str | None = None
    speed_mbps: int | None = None
    poe_status: str | None = None


class VLANSnapshotModel(SnapshotModel):
    """Immutable VLAN snapshot model."""

    vlan_id: int
    name: str
    captured_at: datetime
    version: str = SNAPSHOT_SCHEMA_VERSION
    device_id: str | None = None
    status: str | None = None


class MACTableSnapshotModel(SnapshotModel):
    """Immutable MAC table snapshot model."""

    mac_address: str
    device_id: str
    interface_name: str
    captured_at: datetime
    version: str = SNAPSHOT_SCHEMA_VERSION
    vlan_id: int | None = None
    last_seen: datetime | None = None


class NeighborSnapshotModel(SnapshotModel):
    """Immutable neighbor snapshot model."""

    local_device_id: str
    local_interface: str
    remote_device_id: str
    remote_interface: str | None = None
    protocol: str | None = None
    captured_at: datetime
    version: str = SNAPSHOT_SCHEMA_VERSION


class PowerSnapshotModel(SnapshotModel):
    """Immutable power snapshot model."""

    device_id: str
    source: str
    captured_at: datetime
    version: str = SNAPSHOT_SCHEMA_VERSION
    status: str | None = None
    available_watts: float | None = None
    consumed_watts: float | None = None
    poe_enabled: bool | None = None


class DeviceSnapshotModel(SnapshotModel):
    """Immutable device snapshot model."""

    device_id: str
    name: str
    captured_at: datetime
    version: str = SNAPSHOT_SCHEMA_VERSION
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    product_id: str | None = None
    management_ip: str | None = None
    base_mac: str | None = None
    software_version: str | None = None
    uptime: str | None = None
    hardware_revision: str | None = None
    platform: str | None = None
    stack_members: tuple[str, ...] = Field(default_factory=tuple)
    interfaces: tuple[InterfaceSnapshotModel, ...] = Field(default_factory=tuple)
    vlans: tuple[VLANSnapshotModel, ...] = Field(default_factory=tuple)
    mac_table: tuple[MACTableSnapshotModel, ...] = Field(default_factory=tuple)
    neighbors: tuple[NeighborSnapshotModel, ...] = Field(default_factory=tuple)
    power: PowerSnapshotModel | None = None


class InventorySnapshotModel(SnapshotModel):
    """Immutable inventory snapshot model."""

    devices: tuple[DeviceSnapshotModel, ...] = Field(default_factory=tuple)
    snapshot_id: UUID = Field(default_factory=uuid4)
    captured_at: datetime
    version: str = SNAPSHOT_SCHEMA_VERSION
    source: str | None = None

    @classmethod
    def empty(cls) -> InventorySnapshotModel:
        """Return an empty inventory snapshot."""

        return cls(
            devices=(),
            snapshot_id=uuid4(),
            captured_at=datetime.now(UTC),
        )
