"""Cisco IOS XE platform definitions."""

from __future__ import annotations

from backend.app.transports.base import TransportCapability
from backend.app.vendors.cisco.capabilities import CiscoCapability
from backend.app.vendors.cisco.catalog.commands import build_common_command_catalog
from backend.app.vendors.cisco.catalog.http import build_common_http_catalog
from backend.app.vendors.cisco.catalog.snmp import build_common_snmp_catalog
from backend.app.vendors.cisco.metadata import (
    CiscoPlatformDefinition,
    CiscoPlatformMetadata,
)

CATALYST_2960X = CiscoPlatformDefinition(
    metadata=CiscoPlatformMetadata(
        family="catalyst-2960x",
        display_name="Cisco Catalyst 2960X",
        model_names=("WS-C2960X-24TS-L", "WS-C2960X-48FPS-L"),
        product_ids=("WS-C2960X-24TS-L", "WS-C2960X-48FPS-L"),
        transport_support=frozenset(
            {
                TransportCapability.SSH,
                TransportCapability.SNMP,
                TransportCapability.HTTP,
            }
        ),
        parser_family="iosxe",
        firmware_family="iosxe",
        capabilities=frozenset(
            {
                CiscoCapability.SSH,
                CiscoCapability.SNMP,
                CiscoCapability.HTTP,
                CiscoCapability.CONFIG_BACKUP,
                CiscoCapability.CDP,
                CiscoCapability.LLDP,
                CiscoCapability.VLAN,
                CiscoCapability.MAC_TABLE,
                CiscoCapability.INTERFACE_INVENTORY,
                CiscoCapability.NEIGHBOR_DISCOVERY,
                CiscoCapability.POE,
            }
        ),
    ),
    command_catalog=build_common_command_catalog(),
    snmp_catalog=build_common_snmp_catalog(),
    http_catalog=build_common_http_catalog(),
    platform_strings=("Cisco IOS XE Software", "WS-C2960X"),
    sys_object_ids=("1.3.6.1.4.1.9.1.1510",),
    http_banners=("cisco ios xe",),
)
