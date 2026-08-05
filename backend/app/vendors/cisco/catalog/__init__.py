"""Cisco catalog metadata."""

from backend.app.vendors.cisco.catalog.commands import (
    COMMON_COMMAND_CATALOG,
    CommandCatalog,
    CommandCategory,
    CommandDefinition,
    CommandGroup,
    build_common_command_catalog,
)
from backend.app.vendors.cisco.catalog.http import (
    COMMON_HTTP_CATALOG,
    HttpCatalog,
    HttpEndpointMetadata,
    HttpMethod,
    build_common_http_catalog,
)
from backend.app.vendors.cisco.catalog.snmp import (
    COMMON_SNMP_CATALOG,
    SnmpCatalog,
    SnmpGroup,
    SnmpOidGroup,
    build_common_snmp_catalog,
)

__all__ = [
    "COMMON_COMMAND_CATALOG",
    "COMMON_HTTP_CATALOG",
    "COMMON_SNMP_CATALOG",
    "CommandCatalog",
    "CommandCategory",
    "CommandDefinition",
    "CommandGroup",
    "HttpCatalog",
    "HttpEndpointMetadata",
    "HttpMethod",
    "SnmpCatalog",
    "SnmpGroup",
    "SnmpOidGroup",
    "build_common_command_catalog",
    "build_common_http_catalog",
    "build_common_snmp_catalog",
]
