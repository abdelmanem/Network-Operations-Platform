"""Canonical inventory models and mapping utilities."""

from backend.app.inventory.dto import InventorySnapshot
from backend.app.inventory.entities import (
    VLAN,
    Device,
    DeviceType,
    Interface,
    IPAddress,
    Manufacturer,
    Platform,
    Rack,
    Role,
    Site,
)

__all__ = [
    "Device",
    "DeviceType",
    "IPAddress",
    "Interface",
    "InventorySnapshot",
    "Manufacturer",
    "Platform",
    "Rack",
    "Role",
    "Site",
    "VLAN",
]
