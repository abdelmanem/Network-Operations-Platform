"""Cisco inventory collector factory."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.collectors.cisco.aironet import CiscoAironetInventoryCollector
from backend.app.collectors.cisco.ce500 import CiscoCE500InventoryCollector
from backend.app.collectors.cisco.ios import CiscoIOSInventoryCollector
from backend.app.collectors.registry import CollectorRegistry
from backend.app.transports.manager import TransportManager
from backend.app.vendors.cisco.platforms import CiscoPlatformRegistry, default_registry


@dataclass(slots=True)
class CiscoInventoryCollectorFactory:
    """Create Cisco inventory collectors from platform metadata."""

    transport_manager: TransportManager
    platform_registry: CiscoPlatformRegistry

    @classmethod
    def with_defaults(
        cls,
        transport_manager: TransportManager,
    ) -> CiscoInventoryCollectorFactory:
        """Create a factory using the default Cisco platform registry."""

        return cls(
            transport_manager=transport_manager,
            platform_registry=default_registry(),
        )

    def create(self, platform_family: str) -> CiscoIOSInventoryCollector:
        """Create a collector for a supported platform family."""

        self.platform_registry.get(platform_family)
        return CiscoIOSInventoryCollector(
            platform_family=platform_family,
            transport_manager=self.transport_manager,
            platform_registry=self.platform_registry,
        )

    def create_ce500(self) -> CiscoCE500InventoryCollector:
        """Create a Catalyst Express 500 collector."""

        return CiscoCE500InventoryCollector(
            transport_manager=self.transport_manager,
            platform_registry=self.platform_registry,
        )

    def create_aironet(self) -> CiscoAironetInventoryCollector:
        """Create an Aironet collector."""

        return CiscoAironetInventoryCollector(
            transport_manager=self.transport_manager,
            platform_registry=self.platform_registry,
        )

    def register_all(self, registry: CollectorRegistry) -> None:
        """Register all supported Cisco inventory collectors."""

        registry.register(
            CiscoIOSInventoryCollector(
                name="cisco-catalyst-2960-inventory",
                platform_family="catalyst-2960",
                transport_manager=self.transport_manager,
                platform_registry=self.platform_registry,
            )
        )
        registry.register(
            CiscoIOSInventoryCollector(
                name="cisco-catalyst-2960x-inventory",
                platform_family="catalyst-2960x",
                transport_manager=self.transport_manager,
                platform_registry=self.platform_registry,
            )
        )
        registry.register(
            CiscoIOSInventoryCollector(
                name="cisco-catalyst-3560-inventory",
                platform_family="catalyst-3560",
                transport_manager=self.transport_manager,
                platform_registry=self.platform_registry,
            )
        )
        registry.register(self.create_ce500())
        registry.register(self.create_aironet())


def build_cisco_inventory_registry(
    transport_manager: TransportManager,
) -> CollectorRegistry:
    """Build a collector registry with all Cisco inventory collectors."""

    registry = CollectorRegistry()
    CiscoInventoryCollectorFactory.with_defaults(transport_manager).register_all(
        registry
    )
    return registry
