"""Cisco Catalyst Express 500 inventory collector."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.collectors.cisco.base import CiscoInventoryCollectorBase
from backend.app.discovery.capabilities import CollectorCapability

CE500_INVENTORY_CAPABILITIES = frozenset(
    {
        CollectorCapability.INTERFACES,
        CollectorCapability.VLANS,
        CollectorCapability.POE,
    }
)


@dataclass(slots=True, kw_only=True)
class CiscoCE500InventoryCollector(CiscoInventoryCollectorBase):
    """Inventory collector for Catalyst Express 500 switches."""

    name: str = "cisco-ce500-inventory"
    capabilities: frozenset[CollectorCapability] = CE500_INVENTORY_CAPABILITIES
    platform_family: str = "catalyst-express-500"
