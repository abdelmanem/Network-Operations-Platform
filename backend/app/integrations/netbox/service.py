"""NetBox integration service."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.integrations.netbox.client import NetBoxClient
from backend.app.integrations.netbox.endpoints import NetBoxEndpoint
from backend.app.integrations.netbox.models import (
    NetBoxDevice,
    NetBoxDeviceType,
    NetBoxInterface,
    NetBoxInventoryDataset,
    NetBoxIPAddress,
    NetBoxManufacturer,
    NetBoxPlatform,
    NetBoxRack,
    NetBoxRole,
    NetBoxSite,
    NetBoxStatusResponse,
    NetBoxVLAN,
)


@dataclass(slots=True)
class NetBoxService:
    """Domain-oriented wrapper around the NetBox client."""

    client: NetBoxClient

    async def health(self) -> NetBoxStatusResponse:
        """Return the NetBox status payload."""

        return await self.client.health()

    async def fetch_inventory_dataset(self) -> NetBoxInventoryDataset:
        """Fetch the canonical NetBox inventory data set."""

        return NetBoxInventoryDataset(
            sites=await self.client.list_collection(NetBoxEndpoint.SITES, NetBoxSite),
            racks=await self.client.list_collection(NetBoxEndpoint.RACKS, NetBoxRack),
            devices=await self.client.list_collection(
                NetBoxEndpoint.DEVICES, NetBoxDevice
            ),
            interfaces=await self.client.list_collection(
                NetBoxEndpoint.INTERFACES,
                NetBoxInterface,
            ),
            ip_addresses=await self.client.list_collection(
                NetBoxEndpoint.IP_ADDRESSES,
                NetBoxIPAddress,
            ),
            vlans=await self.client.list_collection(NetBoxEndpoint.VLANS, NetBoxVLAN),
            platforms=await self.client.list_collection(
                NetBoxEndpoint.PLATFORMS,
                NetBoxPlatform,
            ),
            manufacturers=await self.client.list_collection(
                NetBoxEndpoint.MANUFACTURERS,
                NetBoxManufacturer,
            ),
            device_types=await self.client.list_collection(
                NetBoxEndpoint.DEVICE_TYPES,
                NetBoxDeviceType,
            ),
            roles=await self.client.list_collection(
                NetBoxEndpoint.DEVICE_ROLES, NetBoxRole
            ),
        )
