from backend.app.integrations.netbox.mapper import NetBoxInventoryMapper
from backend.app.integrations.netbox.models import (
    NetBoxDevice,
    NetBoxDeviceType,
    NetBoxDeviceTypeReference,
    NetBoxInventoryDataset,
    NetBoxIPAddress,
    NetBoxIPAddressReference,
    NetBoxManufacturer,
    NetBoxObjectReference,
    NetBoxRole,
    NetBoxSite,
)
from backend.app.inventory.mapper import InventoryMapper


def test_inventory_mapper_builds_canonical_snapshot() -> None:
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
                primary_ip4=NetBoxIPAddressReference(
                    id=6,
                    address="192.0.2.10/24",
                    family=4,
                ),
            ),
        ),
        ip_addresses=(
            NetBoxIPAddress(
                id=6,
                address="192.0.2.10/24",
                family=4,
            ),
        ),
    )

    mapper = InventoryMapper(netbox_mapper=NetBoxInventoryMapper())
    snapshot = mapper.to_snapshot(dataset)

    assert snapshot.sites[0].name == "Site A"
    assert snapshot.manufacturers[0].name == "Cisco"
    assert snapshot.devices[0].primary_ip == "192.0.2.10/24"
