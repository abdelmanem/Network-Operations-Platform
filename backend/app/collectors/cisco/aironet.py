"""Cisco Aironet inventory collector."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.collectors.cisco.base import CiscoInventoryCollectorBase
from backend.app.discovery.capabilities import CollectorCapability

AIRONET_INVENTORY_CAPABILITIES = frozenset(
    {
        CollectorCapability.INTERFACES,
        CollectorCapability.VLANS,
    }
)


@dataclass(slots=True, kw_only=True)
class CiscoAironetInventoryCollector(CiscoInventoryCollectorBase):
    """Inventory collector for Cisco Aironet access points."""

    name: str = "cisco-aironet-inventory"
    capabilities: frozenset[CollectorCapability] = AIRONET_INVENTORY_CAPABILITIES
    platform_family: str = "aironet-1131"
