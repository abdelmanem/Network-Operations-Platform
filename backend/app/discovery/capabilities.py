"""Collector capability definitions."""

from __future__ import annotations

from enum import StrEnum


class CollectorCapability(StrEnum):
    """Capabilities that collectors may advertise."""

    SSH = "SSH"
    TELNET = "TELNET"
    SNMP = "SNMP"
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    CDP = "CDP"
    LLDP = "LLDP"
    CONFIG_BACKUP = "CONFIG_BACKUP"
    INTERFACES = "INTERFACES"
    VLANS = "VLANS"
    MAC_TABLE = "MAC_TABLE"
    ARP_TABLE = "ARP_TABLE"
    POWER = "POWER"
    POE = "POE"


TRANSPORT_TO_COLLECTOR_CAPABILITY: dict[str, CollectorCapability] = {
    "ssh": CollectorCapability.SSH,
    "telnet": CollectorCapability.TELNET,
    "snmp": CollectorCapability.SNMP,
    "http": CollectorCapability.HTTP,
    "https": CollectorCapability.HTTPS,
}

