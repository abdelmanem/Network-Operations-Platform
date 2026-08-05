"""Cisco Catalyst Express 500 platform definitions."""

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

CATALYST_EXPRESS_500 = CiscoPlatformDefinition(
    metadata=CiscoPlatformMetadata(
        family="catalyst-express-500",
        display_name="Cisco Catalyst Express 500",
        model_names=("WS-CE500-24TT", "WS-CE500-24LC"),
        product_ids=("WS-CE500-24TT", "WS-CE500-24LC"),
        transport_support=frozenset(
            {TransportCapability.HTTP, TransportCapability.SNMP}
        ),
        parser_family="ce500",
        firmware_family="ce500",
        capabilities=frozenset(
            {
                CiscoCapability.HTTP,
                CiscoCapability.SNMP,
                CiscoCapability.CONFIG_BACKUP,
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
    platform_strings=("Cisco Catalyst Express 500", "WS-CE500"),
    sys_object_ids=("1.3.6.1.4.1.9.1.748",),
    http_banners=("cisco catalyst express",),
)
