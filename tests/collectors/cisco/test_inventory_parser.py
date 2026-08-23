from __future__ import annotations

from pathlib import Path

import pytest
from backend.app.collectors.cisco.inventory import CiscoInventoryParser
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.context import ParserContext, ParserInputFormat

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "cisco"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_cisco_inventory_parser_maps_fixture_payload_to_snapshot() -> None:
    parser = CiscoInventoryParser()
    payload = {
        "target": {
            "identifier": "switch-1",
            "address": "10.0.0.10",
            "metadata": {"platform_family": "catalyst-2960x"},
        },
        "platform_family": "catalyst-2960x",
        "parser_family": "iosxe",
        "transport": "netmiko",
        "transport_capability": "SSH",
        "commands": {
            "show version": _fixture("show_version_2960x.txt"),
            "show inventory": _fixture("show_inventory_2960x.txt"),
            "show interfaces status": _fixture("show_interfaces_status_2960x.txt"),
            "show vlan brief": _fixture("show_vlan_brief_2960x.txt"),
            "show power inline": _fixture("show_power_inline_2960x.txt"),
            "show cdp neighbors detail": _fixture(
                "show_cdp_neighbors_detail_2960x.txt"
            ),
        },
    }
    context = ParserContext(
        source="switch-1",
        input_format=ParserInputFormat.JSON,
        parser_name=parser.name,
    )

    result = parser.parse(context, payload)
    snapshot = NormalizationEngine().normalize(result).snapshot

    assert result.parser_name == "cisco-inventory-parser"
    assert {record.kind for record in result.records} >= {
        "device",
        "interface",
        "vlan",
        "neighbor",
        "power",
    }
    device = snapshot.devices[0]
    assert device.name == "Switch"
    assert device.model == "WS-C2960X-48FPS-L"
    assert device.serial_number == "FOC1234X1AB"
    assert device.management_ip == "10.0.0.10"
    assert device.software_version == "15.2(7)E7"
    assert len(device.interfaces) == 2
    assert device.vlans[1].vlan_id == 10
    assert device.neighbors[0].remote_device_id == "core-switch"
    assert device.power is not None
    assert device.power.available_watts == 370.0


@pytest.mark.parametrize(
    ("port_line", "expected_remote_interface"),
    [
        ("Port ID: GigabitEthernet1/0/24", "GigabitEthernet1/0/24"),
        ("Port Description", None),
    ],
)
def test_lldp_port_labels_without_or_with_colon_do_not_crash_parsing(
    port_line: str,
    expected_remote_interface: str | None,
) -> None:
    parser = CiscoInventoryParser()
    payload = {
        "target": {"identifier": "switch-1", "address": "10.0.0.10"},
        "commands": {
            "show lldp neighbors detail": (
                "System Name: core-switch\n"
                "Interface: GigabitEthernet1/0/1, Port ID: ignored\n"
                f"{port_line}\n"
            )
        },
    }

    result = parser.parse(
        ParserContext(
            source="switch-1",
            input_format=ParserInputFormat.JSON,
            parser_name=parser.name,
        ),
        payload,
    )

    neighbor = next(record for record in result.records if record.kind == "neighbor")
    assert neighbor.payload["remote_interface"] == expected_remote_interface
