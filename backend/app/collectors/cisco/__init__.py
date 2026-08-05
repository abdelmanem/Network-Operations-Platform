"""Cisco inventory collector package."""

from backend.app.collectors.cisco.aironet import CiscoAironetInventoryCollector
from backend.app.collectors.cisco.base import CiscoInventoryCollectorBase
from backend.app.collectors.cisco.ce500 import CiscoCE500InventoryCollector
from backend.app.collectors.cisco.factory import (
    CiscoInventoryCollectorFactory,
    build_cisco_inventory_registry,
)
from backend.app.collectors.cisco.inventory import CiscoInventoryParser
from backend.app.collectors.cisco.ios import CiscoIOSInventoryCollector

__all__ = [
    "CiscoAironetInventoryCollector",
    "CiscoCE500InventoryCollector",
    "CiscoIOSInventoryCollector",
    "CiscoInventoryCollectorBase",
    "CiscoInventoryCollectorFactory",
    "CiscoInventoryParser",
    "build_cisco_inventory_registry",
]
