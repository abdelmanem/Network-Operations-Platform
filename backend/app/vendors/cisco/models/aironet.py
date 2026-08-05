"""Cisco Aironet platform definitions."""

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

AIRONET_1131 = CiscoPlatformDefinition(
    metadata=CiscoPlatformMetadata(
        family="aironet-1131",
        display_name="Cisco Aironet 1131",
        model_names=("AIR-AP1131AG-A-K9", "AIR-AP1131G-A-K9"),
        product_ids=("AIR-AP1131AG-A-K9", "AIR-AP1131G-A-K9"),
        transport_support=frozenset(
            {TransportCapability.SNMP, TransportCapability.HTTP}
        ),
        parser_family="aironet",
        firmware_family="aironet",
        capabilities=frozenset(
            {
                CiscoCapability.SNMP,
                CiscoCapability.HTTP,
                CiscoCapability.CONFIG_BACKUP,
                CiscoCapability.VLAN,
                CiscoCapability.INTERFACE_INVENTORY,
                CiscoCapability.NEIGHBOR_DISCOVERY,
            }
        ),
    ),
    command_catalog=build_common_command_catalog(),
    snmp_catalog=build_common_snmp_catalog(),
    http_catalog=build_common_http_catalog(),
    platform_strings=("Cisco Aironet", "AIR-AP1131"),
    sys_object_ids=("1.3.6.1.4.1.9.1.928",),
    http_banners=("cisco aironet",),
)
