"""Mapping helpers from NetBox payloads to canonical inventory models."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.integrations.netbox.mapper import NetBoxInventoryMapper
from backend.app.integrations.netbox.models import NetBoxInventoryDataset
from backend.app.inventory.dto import InventorySnapshot


@dataclass(slots=True)
class InventoryMapper:
    """Map validated NetBox objects into canonical inventory objects."""

    netbox_mapper: NetBoxInventoryMapper

    def to_snapshot(self, dataset: NetBoxInventoryDataset) -> InventorySnapshot:
        """Convert NetBox inventory data into a canonical snapshot."""

        return InventorySnapshot(
            sites=tuple(self.netbox_mapper.site(site) for site in dataset.sites),
            racks=tuple(self.netbox_mapper.rack(rack) for rack in dataset.racks),
            devices=tuple(
                self.netbox_mapper.device(device) for device in dataset.devices
            ),
            interfaces=tuple(
                self.netbox_mapper.interface(interface)
                for interface in dataset.interfaces
            ),
            ip_addresses=tuple(
                self.netbox_mapper.ip_address(ip_address)
                for ip_address in dataset.ip_addresses
            ),
            vlans=tuple(self.netbox_mapper.vlan(vlan) for vlan in dataset.vlans),
            platforms=tuple(
                self.netbox_mapper.platform(platform) for platform in dataset.platforms
            ),
            manufacturers=tuple(
                self.netbox_mapper.manufacturer(manufacturer)
                for manufacturer in dataset.manufacturers
            ),
            device_types=tuple(
                self.netbox_mapper.device_type(device_type)
                for device_type in dataset.device_types
            ),
            roles=tuple(self.netbox_mapper.role(role) for role in dataset.roles),
        )
