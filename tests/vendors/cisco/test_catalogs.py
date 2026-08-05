from __future__ import annotations

from backend.app.vendors.cisco.catalog.commands import CommandCategory
from backend.app.vendors.cisco.catalog.http import HttpMethod
from backend.app.vendors.cisco.catalog.snmp import SnmpGroup
from backend.app.vendors.cisco.models.ios import CATALYST_2960


def test_command_catalog_lookup_returns_expected_commands() -> None:
    commands = CATALYST_2960.command_catalog.commands(CommandCategory.INTERFACES)

    assert [command.command for command in commands] == [
        "show interfaces status",
        "show interfaces counters",
    ]
    assert (
        CommandCategory.RUNNING_CONFIGURATION
        in CATALYST_2960.command_catalog.categories()
    )


def test_snmp_and_http_catalog_lookup_returns_metadata() -> None:
    assert CATALYST_2960.snmp_catalog.oids(SnmpGroup.SYSTEM) == ("1.3.6.1.2.1.1",)
    assert CATALYST_2960.http_catalog.paths() == ("/", "/status")
    assert CATALYST_2960.http_catalog.endpoints[0].method == HttpMethod.GET
