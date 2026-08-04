"""Inventory transfer objects."""

from __future__ import annotations

from pydantic import Field

from backend.app.inventory.entities import (
    VLAN,
    Device,
    DeviceType,
    Interface,
    InventoryModel,
    IPAddress,
    Manufacturer,
    Platform,
    Rack,
    Role,
    Site,
)


class InventorySnapshot(InventoryModel):
    """Immutable snapshot of canonical inventory entities."""

    sites: tuple[Site, ...] = Field(default_factory=tuple)
    racks: tuple[Rack, ...] = Field(default_factory=tuple)
    devices: tuple[Device, ...] = Field(default_factory=tuple)
    interfaces: tuple[Interface, ...] = Field(default_factory=tuple)
    ip_addresses: tuple[IPAddress, ...] = Field(default_factory=tuple)
    vlans: tuple[VLAN, ...] = Field(default_factory=tuple)
    platforms: tuple[Platform, ...] = Field(default_factory=tuple)
    manufacturers: tuple[Manufacturer, ...] = Field(default_factory=tuple)
    device_types: tuple[DeviceType, ...] = Field(default_factory=tuple)
    roles: tuple[Role, ...] = Field(default_factory=tuple)
