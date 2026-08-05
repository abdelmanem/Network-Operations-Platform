"""Cisco IOS platform definitions."""

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

CATALYST_2960 = CiscoPlatformDefinition(
    metadata=CiscoPlatformMetadata(
        family="catalyst-2960",
        display_name="Cisco Catalyst 2960",
        model_names=("WS-C2960-24TT-L", "WS-C2960-48TT-L"),
        product_ids=("WS-C2960-24TT-L", "WS-C2960-48TT-L"),
        transport_support=frozenset(
            {TransportCapability.SSH, TransportCapability.SNMP}
        ),
        parser_family="ios",
        firmware_family="ios",
        capabilities=frozenset(
            {
                CiscoCapability.SSH,
                CiscoCapability.SNMP,
                CiscoCapability.CONFIG_BACKUP,
                CiscoCapability.CDP,
                CiscoCapability.LLDP,
                CiscoCapability.VLAN,
                CiscoCapability.MAC_TABLE,
                CiscoCapability.INTERFACE_INVENTORY,
                CiscoCapability.NEIGHBOR_DISCOVERY,
            }
        ),
    ),
    command_catalog=build_common_command_catalog(),
    snmp_catalog=build_common_snmp_catalog(),
    http_catalog=build_common_http_catalog(),
    platform_strings=("Cisco IOS Software", "WS-C2960"),
    sys_object_ids=("1.3.6.1.4.1.9.1.516",),
    http_banners=("cisco ios",),
)


CATALYST_3560 = CiscoPlatformDefinition(
    metadata=CiscoPlatformMetadata(
        family="catalyst-3560",
        display_name="Cisco Catalyst 3560",
        model_names=("WS-C3560-24PS-S", "WS-C3560-48PS-S"),
        product_ids=("WS-C3560-24PS-S", "WS-C3560-48PS-S"),
        transport_support=frozenset(
            {TransportCapability.SSH, TransportCapability.SNMP}
        ),
        parser_family="ios",
        firmware_family="ios",
        capabilities=frozenset(
            {
                CiscoCapability.SSH,
                CiscoCapability.SNMP,
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
    platform_strings=("Cisco IOS Software", "WS-C3560"),
    sys_object_ids=("1.3.6.1.4.1.9.1.517",),
    http_banners=("cisco ios",),
)
