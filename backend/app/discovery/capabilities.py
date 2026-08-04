"""Collector capability definitions."""

from __future__ import annotations

from enum import StrEnum


class CollectorCapability(StrEnum):
    """Capabilities that collectors may advertise."""

    SSH = "SSH"
    SNMP = "SNMP"
    HTTP = "HTTP"
    CDP = "CDP"
    LLDP = "LLDP"
    CONFIG_BACKUP = "CONFIG_BACKUP"
    INTERFACES = "INTERFACES"
    VLANS = "VLANS"
    MAC_TABLE = "MAC_TABLE"
    ARP_TABLE = "ARP_TABLE"
    POWER = "POWER"
    POE = "POE"
