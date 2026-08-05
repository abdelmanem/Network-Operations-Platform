from __future__ import annotations

import json
from pathlib import Path

from backend.app.comparison import (
    ComparisonEngine,
    DifferenceFilter,
    DifferenceType,
    InventoryMatcher,
)
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import (
    VLAN,
    Device,
    DeviceType,
    Interface,
    Manufacturer,
    Platform,
)
from backend.app.snapshot.entities import (
    DeviceSnapshot,
    InterfaceSnapshot,
    NeighborSnapshot,
    VLANSnapshot,
)
from backend.app.snapshot.entities import (
    InventorySnapshot as LiveInventorySnapshot,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "comparison"


def _netbox_snapshot() -> NetBoxInventorySnapshot:
    manufacturer = Manufacturer(name="Cisco", slug="cisco")
    device_type = DeviceType(
        manufacturer=manufacturer,
        model="WS-C2960X-48FPS-L",
        slug="ws-c2960x-48fps-l",
    )
    return NetBoxInventorySnapshot(
        manufacturers=(manufacturer,),
        device_types=(device_type,),
        platforms=(Platform(name="Cisco IOS XE", slug="iosxe"),),
        devices=(
            Device(
                name="switch-01",
                device_type=device_type,
                platform=Platform(name="Cisco IOS XE", slug="iosxe"),
                serial="NETBOX123",
                primary_ip="10.0.0.10/32",
                interfaces=(
                    Interface(name="Gi1/0/1", device_name="switch-01", enabled=True),
                    Interface(name="Gi1/0/2", device_name="switch-01", enabled=True),
                ),
            ),
        ),
        vlans=(VLAN(vid=10, name="users", status="active"),),
    )


def _live_snapshot() -> LiveInventorySnapshot:
    return LiveInventorySnapshot(
        source="collector",
        devices=(
            DeviceSnapshot(
                device_id="switch-01",
                name="switch-01",
                manufacturer="Cisco",
                model="WS-C2960X-48FPS-L",
                serial_number="LIVE999",
                management_ip="10.0.0.11",
                platform="ios",
                interfaces=(
                    InterfaceSnapshot(
                        device_id="switch-01",
                        name="Gi1/0/1",
                        admin_status="up",
                    ),
                    InterfaceSnapshot(
                        device_id="switch-01",
                        name="Gi1/0/3",
                        admin_status="up",
                    ),
                ),
                vlans=(
                    VLANSnapshot(vlan_id=10, name="staff", device_id="switch-01"),
                    VLANSnapshot(vlan_id=20, name="voice", device_id="switch-01"),
                ),
                neighbors=(
                    NeighborSnapshot(
                        local_device_id="switch-01",
                        local_interface="Gi1/0/1",
                        remote_device_id="core-switch",
                    ),
                ),
            ),
        ),
    )


def test_inventory_matcher_matches_by_name_and_tracks_unmatched_devices() -> None:
    netbox = _netbox_snapshot()
    live = LiveInventorySnapshot(
        devices=(
            _live_snapshot().devices[0],
            DeviceSnapshot(device_id="rogue-1", name="rogue-1"),
        )
    )

    match = InventoryMatcher().match(netbox, live)

    assert len(match.matched_devices) == 1
    assert not match.missing_devices
    assert match.unexpected_devices[0].name == "rogue-1"


def test_comparison_engine_produces_golden_differences_and_findings() -> None:
    result = ComparisonEngine().compare(_netbox_snapshot(), _live_snapshot())
    expected_keys = json.loads(
        (FIXTURES / "golden_differences.json").read_text(encoding="utf-8")
    )

    assert [difference.key for difference in result.differences] == expected_keys
    assert len(result.findings) == len(result.differences)
    assert result.metrics is not None
    assert result.metrics.modified == 4
    assert result.metrics.missing == 1
    assert result.metrics.unexpected == 2
    assert result.metrics.unsupported == 1
    assert result.is_compliant is False
    assert result.findings[0].evidence[0].reference == result.differences[0].key


def test_difference_filter_limits_result_scope() -> None:
    engine = ComparisonEngine(
        difference_filter=DifferenceFilter(
            include_types=frozenset({DifferenceType.MODIFIED})
        )
    )

    result = engine.compare(_netbox_snapshot(), _live_snapshot())

    assert result.metrics is not None
    assert result.metrics.total_differences == 4
    assert all(
        difference.difference_type == DifferenceType.MODIFIED
        for difference in result.differences
    )


def test_comparison_engine_returns_compliant_result_when_inventory_matches() -> None:
    netbox = _netbox_snapshot()
    live = LiveInventorySnapshot(
        devices=(
            DeviceSnapshot(
                device_id="switch-01",
                name="switch-01",
                model="WS-C2960X-48FPS-L",
                serial_number="NETBOX123",
                management_ip="10.0.0.10/32",
                platform="Cisco IOS XE",
                interfaces=(
                    InterfaceSnapshot(
                        device_id="switch-01",
                        name="Gi1/0/1",
                        admin_status="up",
                    ),
                    InterfaceSnapshot(
                        device_id="switch-01",
                        name="Gi1/0/2",
                        admin_status="up",
                    ),
                ),
                vlans=(VLANSnapshot(vlan_id=10, name="users", status="active"),),
            ),
        )
    )

    result = ComparisonEngine().compare(netbox, live)

    assert result.is_compliant is True
    assert result.findings == ()
    assert result.metrics is not None
    assert result.metrics.total_differences == 0
