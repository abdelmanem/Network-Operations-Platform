import pytest
from backend.app.cache.redis import InMemoryCache
from backend.app.config.settings import get_settings
from backend.app.integrations.netbox.mapper import NetBoxInventoryMapper
from backend.app.integrations.netbox.models import (
    NetBoxDevice,
    NetBoxDeviceType,
    NetBoxDeviceTypeReference,
    NetBoxInventoryDataset,
    NetBoxManufacturer,
    NetBoxObjectReference,
    NetBoxRole,
    NetBoxSite,
)
from backend.app.inventory.mapper import InventoryMapper
from backend.app.services.base import ServiceContext
from backend.app.services.inventory import InventoryService


class FakeNetBoxService:
    def __init__(self, dataset: NetBoxInventoryDataset) -> None:
        self.dataset = dataset
        self.calls = 0

    async def fetch_inventory_dataset(self) -> NetBoxInventoryDataset:
        self.calls += 1
        return self.dataset


@pytest.mark.anyio
async def test_inventory_service_caches_snapshot() -> None:
    dataset = NetBoxInventoryDataset(
        sites=(NetBoxSite(id=1, name="Site A", slug="site-a"),),
        manufacturers=(NetBoxManufacturer(id=2, name="Cisco", slug="cisco"),),
        device_types=(
            NetBoxDeviceType(
                id=3,
                manufacturer=NetBoxObjectReference(id=2, name="Cisco", slug="cisco"),
                model="WS-C2960X",
                slug="ws-c2960x",
            ),
        ),
        roles=(NetBoxRole(id=4, name="Access", slug="access"),),
        devices=(
            NetBoxDevice(
                id=5,
                name="switch-01",
                device_type=NetBoxDeviceTypeReference(
                    id=3,
                    model="WS-C2960X",
                    slug="ws-c2960x",
                    manufacturer=NetBoxObjectReference(
                        id=2, name="Cisco", slug="cisco"
                    ),
                ),
                role=NetBoxObjectReference(id=4, name="Access", slug="access"),
            ),
        ),
    )
    netbox_service = FakeNetBoxService(dataset)
    inventory_service = InventoryService(
        context=ServiceContext(settings=get_settings()),
        netbox_service=netbox_service,
        inventory_mapper=InventoryMapper(netbox_mapper=NetBoxInventoryMapper()),
        cache=InMemoryCache(),
    )

    first = await inventory_service.synchronize()
    second = await inventory_service.synchronize()

    assert first == second
    assert netbox_service.calls == 1
    assert first.devices[0].name == "switch-01"
