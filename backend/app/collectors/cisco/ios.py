"""Cisco IOS and IOS XE inventory collectors."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.collectors.cisco.base import CiscoInventoryCollectorBase
from backend.app.discovery.capabilities import CollectorCapability

IOS_INVENTORY_CAPABILITIES = frozenset(
    {
        CollectorCapability.INTERFACES,
        CollectorCapability.VLANS,
        CollectorCapability.CDP,
        CollectorCapability.LLDP,
        CollectorCapability.POE,
    }
)


@dataclass(slots=True, kw_only=True)
class CiscoIOSInventoryCollector(CiscoInventoryCollectorBase):
    """Inventory collector for Cisco Catalyst IOS/IOS XE switches."""

    name: str = "cisco-ios-inventory"
    capabilities: frozenset[CollectorCapability] = IOS_INVENTORY_CAPABILITIES
    platform_family: str = "catalyst-2960x"
