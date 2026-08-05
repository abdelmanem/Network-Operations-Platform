"""Cisco command catalogs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CommandCategory(StrEnum):
    """Cisco command catalog categories."""

    INVENTORY = "inventory"
    SYSTEM = "system"
    INTERFACES = "interfaces"
    VLANS = "vlans"
    MAC_TABLE = "mac_table"
    ARP = "arp"
    POWER = "power"
    POE = "poe"
    NEIGHBORS = "neighbors"
    VERSION = "version"
    RUNNING_CONFIGURATION = "running_configuration"
    STARTUP_CONFIGURATION = "startup_configuration"
    ENVIRONMENT = "environment"


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    """Define a Cisco command without executing it."""

    command: str
    description: str


@dataclass(frozen=True, slots=True)
class CommandGroup:
    """Group commands by category."""

    category: CommandCategory
    commands: tuple[CommandDefinition, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CommandCatalog:
    """Immutable Cisco command catalog."""

    groups: tuple[CommandGroup, ...] = field(default_factory=tuple)

    def commands(self, category: CommandCategory) -> tuple[CommandDefinition, ...]:
        """Return commands for a category."""

        for group in self.groups:
            if group.category == category:
                return group.commands
        return ()

    def categories(self) -> tuple[CommandCategory, ...]:
        """Return catalog categories."""

        return tuple(group.category for group in self.groups)


COMMON_COMMAND_CATALOG = CommandCatalog(
    groups=(
        CommandGroup(
            category=CommandCategory.INVENTORY,
            commands=(
                CommandDefinition(
                    command="show inventory",
                    description="Display inventory information.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.SYSTEM,
            commands=(
                CommandDefinition(
                    command="show version",
                    description="Display system and firmware details.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.INTERFACES,
            commands=(
                CommandDefinition(
                    command="show interfaces status",
                    description="Display interface status information.",
                ),
                CommandDefinition(
                    command="show interfaces counters",
                    description="Display interface counters.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.VLANS,
            commands=(
                CommandDefinition(
                    command="show vlan brief",
                    description="Display VLAN membership.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.MAC_TABLE,
            commands=(
                CommandDefinition(
                    command="show mac address-table",
                    description="Display MAC address table entries.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.ARP,
            commands=(
                CommandDefinition(
                    command="show ip arp",
                    description="Display ARP table entries.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.POWER,
            commands=(
                CommandDefinition(
                    command="show power inline",
                    description="Display power supply and PoE data.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.POE,
            commands=(
                CommandDefinition(
                    command="show power inline",
                    description="Display PoE status.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.NEIGHBORS,
            commands=(
                CommandDefinition(
                    command="show cdp neighbors detail",
                    description="Display CDP neighbors.",
                ),
                CommandDefinition(
                    command="show lldp neighbors detail",
                    description="Display LLDP neighbors.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.VERSION,
            commands=(
                CommandDefinition(
                    command="show version",
                    description="Display software version.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.RUNNING_CONFIGURATION,
            commands=(
                CommandDefinition(
                    command="show running-config",
                    description="Display the running configuration.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.STARTUP_CONFIGURATION,
            commands=(
                CommandDefinition(
                    command="show startup-config",
                    description="Display the startup configuration.",
                ),
            ),
        ),
        CommandGroup(
            category=CommandCategory.ENVIRONMENT,
            commands=(
                CommandDefinition(
                    command="show environment all",
                    description="Display environmental telemetry.",
                ),
            ),
        ),
    )
)


def build_common_command_catalog() -> CommandCatalog:
    """Return the shared Cisco command catalog."""

    return COMMON_COMMAND_CATALOG
