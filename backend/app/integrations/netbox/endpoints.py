"""Central NetBox REST endpoint registry."""

from __future__ import annotations

from enum import StrEnum


class NetBoxEndpoint(StrEnum):
    """Strongly typed NetBox REST endpoints."""

    STATUS = "/api/status/"
    SITES = "/api/dcim/sites/"
    REGIONS = "/api/dcim/regions/"
    LOCATIONS = "/api/dcim/locations/"
    RACKS = "/api/dcim/racks/"
    MANUFACTURERS = "/api/dcim/manufacturers/"
    DEVICE_TYPES = "/api/dcim/device-types/"
    DEVICE_ROLES = "/api/dcim/device-roles/"
    PLATFORMS = "/api/dcim/platforms/"
    DEVICES = "/api/dcim/devices/"
    INTERFACES = "/api/dcim/interfaces/"
    IP_ADDRESSES = "/api/ipam/ip-addresses/"
    VLANS = "/api/ipam/vlans/"
    PREFIXES = "/api/ipam/prefixes/"
    VRFS = "/api/ipam/vrfs/"
    CABLES = "/api/dcim/cables/"
    CONNECTIONS = "/api/dcim/connections/"

    def __str__(self) -> str:
        return self.value
