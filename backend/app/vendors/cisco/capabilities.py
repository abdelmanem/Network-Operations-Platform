"""Cisco capability models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from backend.app.transports.base import TransportCapability

if TYPE_CHECKING:
    from backend.app.vendors.cisco.platforms import CiscoPlatformRegistry


def _default_registry() -> CiscoPlatformRegistry:
    from backend.app.vendors.cisco.platforms import default_registry

    return default_registry()


class CiscoCapability(StrEnum):
    """Cisco platform capabilities."""

    SSH = "SSH"
    SNMP = "SNMP"
    HTTP = "HTTP"
    CONFIG_BACKUP = "CONFIG_BACKUP"
    CDP = "CDP"
    LLDP = "LLDP"
    POE = "POE"
    VLAN = "VLAN"
    MAC_TABLE = "MAC_TABLE"
    INTERFACE_INVENTORY = "INTERFACE_INVENTORY"
    NEIGHBOR_DISCOVERY = "NEIGHBOR_DISCOVERY"


@dataclass(frozen=True, slots=True)
class CiscoCapabilityMatrix:
    """Capability lookup for Cisco platform definitions."""

    registry: CiscoPlatformRegistry = field(default_factory=_default_registry)

    def supports(self, platform_family: str, capability: CiscoCapability) -> bool:
        """Return whether a platform advertises a capability."""

        definition = self.registry.get(platform_family)
        return capability in definition.metadata.capabilities

    def transport_support(self, platform_family: str) -> frozenset[TransportCapability]:
        """Return transport support for a platform."""

        definition = self.registry.get(platform_family)
        return definition.metadata.transport_support

    def capabilities(self, platform_family: str) -> frozenset[CiscoCapability]:
        """Return all capabilities for a platform."""

        definition = self.registry.get(platform_family)
        return definition.metadata.capabilities
