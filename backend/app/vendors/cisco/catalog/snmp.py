"""Cisco SNMP catalogs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SnmpGroup(StrEnum):
    """Cisco SNMP catalog groups."""

    INVENTORY = "inventory"
    SYSTEM = "system"
    INTERFACES = "interfaces"
    VLANS = "vlans"
    MAC_TABLE = "mac_table"
    ARP = "arp"
    POWER = "power"
    POE = "poe"
    NEIGHBORS = "neighbors"


@dataclass(frozen=True, slots=True)
class SnmpOidGroup:
    """Immutable SNMP OID group."""

    group: SnmpGroup
    oids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SnmpCatalog:
    """Immutable SNMP catalog."""

    groups: tuple[SnmpOidGroup, ...] = field(default_factory=tuple)

    def oids(self, group: SnmpGroup) -> tuple[str, ...]:
        """Return OIDs for a group."""

        for entry in self.groups:
            if entry.group == group:
                return entry.oids
        return ()

    def groups_names(self) -> tuple[SnmpGroup, ...]:
        """Return catalog group names."""

        return tuple(entry.group for entry in self.groups)


COMMON_SNMP_CATALOG = SnmpCatalog(
    groups=(
        SnmpOidGroup(
            group=SnmpGroup.SYSTEM,
            oids=("1.3.6.1.2.1.1",),
        ),
        SnmpOidGroup(
            group=SnmpGroup.INVENTORY,
            oids=("1.3.6.1.2.1.47",),
        ),
        SnmpOidGroup(
            group=SnmpGroup.INTERFACES,
            oids=("1.3.6.1.2.1.2",),
        ),
        SnmpOidGroup(
            group=SnmpGroup.VLANS,
            oids=("1.3.6.1.2.1.17",),
        ),
        SnmpOidGroup(
            group=SnmpGroup.MAC_TABLE,
            oids=("1.3.6.1.2.1.17.4.3",),
        ),
        SnmpOidGroup(
            group=SnmpGroup.ARP,
            oids=("1.3.6.1.2.1.4.22",),
        ),
        SnmpOidGroup(
            group=SnmpGroup.POWER,
            oids=("1.3.6.1.4.1.9.9.402",),
        ),
        SnmpOidGroup(
            group=SnmpGroup.POE,
            oids=("1.3.6.1.4.1.9.9.402.1",),
        ),
        SnmpOidGroup(
            group=SnmpGroup.NEIGHBORS,
            oids=("1.3.6.1.4.1.9.9.23",),
        ),
    )
)


def build_common_snmp_catalog() -> SnmpCatalog:
    """Return the shared Cisco SNMP catalog."""

    return COMMON_SNMP_CATALOG
