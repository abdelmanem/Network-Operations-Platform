"""Schemas for snapshot detail API responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SnapshotResponse(BaseModel):
    """Snapshot metadata and summary."""

    id: UUID
    source: str = Field(description="Source: 'NETBOX' or 'LIVE'")
    device_count: int = Field(description="Number of devices in snapshot")
    interface_count: int = Field(description="Number of interfaces in snapshot")
    vlan_count: int = Field(description="Number of VLANs in snapshot")
    neighbor_count: int = Field(description="Number of neighbors in snapshot")
    captured_at: datetime


class InterfaceResponse(BaseModel):
    """Interface from a device snapshot."""

    name: str
    admin_status: str | None = None
    oper_status: str | None = None
    description: str | None = None
    mac_address: str | None = None
    speed_mbps: int | None = None
    poe_status: str | None = None


class InterfaceListResponse(BaseModel):
    """List of interfaces for a device."""

    snapshot_id: UUID
    device_id: str
    interface_count: int
    items: list[InterfaceResponse] = Field(default_factory=list)


class VlanResponse(BaseModel):
    """VLAN from a device snapshot."""

    vlan_id: int
    name: str
    status: str | None = None


class VlanListResponse(BaseModel):
    """List of VLANs for a device."""

    snapshot_id: UUID
    device_id: str
    vlan_count: int
    items: list[VlanResponse] = Field(default_factory=list)


class NeighborResponse(BaseModel):
    """Neighbor relationship from device discovery."""

    neighbor_id: str = Field(description="Remote device ID")
    remote_device_id: str
    remote_interface: str | None = None
    local_interface: str | None = None
    protocol: str | None = None


class NeighborListResponse(BaseModel):
    """List of neighbors for a device."""

    snapshot_id: UUID
    device_id: str
    neighbor_count: int
    items: list[NeighborResponse] = Field(default_factory=list)


class SnapshotDeviceListResponse(BaseModel):
    """List of devices in a snapshot."""

    snapshot_id: UUID
    source: str
    device_count: int
    items: list[dict[str, object]] = Field(default_factory=list)
