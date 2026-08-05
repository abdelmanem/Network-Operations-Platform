"""Cisco platform metadata."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.transports.base import TransportCapability
from backend.app.vendors.cisco.capabilities import CiscoCapability
from backend.app.vendors.cisco.catalog.commands import CommandCatalog
from backend.app.vendors.cisco.catalog.http import HttpCatalog
from backend.app.vendors.cisco.catalog.snmp import SnmpCatalog


@dataclass(frozen=True, slots=True)
class CiscoPlatformMetadata:
    """Immutable Cisco platform metadata."""

    family: str
    display_name: str
    model_names: tuple[str, ...] = field(default_factory=tuple)
    product_ids: tuple[str, ...] = field(default_factory=tuple)
    transport_support: frozenset[TransportCapability] = field(default_factory=frozenset)
    parser_family: str = ""
    firmware_family: str = ""
    capabilities: frozenset[CiscoCapability] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.family.strip():
            raise ValueError("Cisco platform family must not be empty.")
        if not self.display_name.strip():
            raise ValueError("Cisco platform display name must not be empty.")
        if not self.model_names:
            raise ValueError("Cisco platform must define at least one model name.")
        if not self.product_ids:
            raise ValueError("Cisco platform must define at least one product id.")
        if not self.transport_support:
            raise ValueError("Cisco platform must define transport support.")
        if not self.parser_family.strip():
            raise ValueError("Cisco platform parser family must not be empty.")
        if not self.firmware_family.strip():
            raise ValueError("Cisco platform firmware family must not be empty.")
        if not self.capabilities:
            raise ValueError("Cisco platform must define at least one capability.")


@dataclass(frozen=True, slots=True)
class CiscoPlatformDefinition:
    """Bundle Cisco metadata, detection hints, and catalogs."""

    metadata: CiscoPlatformMetadata
    command_catalog: CommandCatalog
    snmp_catalog: SnmpCatalog
    http_catalog: HttpCatalog
    platform_strings: tuple[str, ...] = field(default_factory=tuple)
    sys_object_ids: tuple[str, ...] = field(default_factory=tuple)
    http_banners: tuple[str, ...] = field(default_factory=tuple)

    @property
    def family(self) -> str:
        """Return the platform family identifier."""

        return self.metadata.family

    def matches_model(self, value: str) -> bool:
        """Return whether a model string matches this platform."""

        normalized = value.strip().lower()
        return normalized in {item.lower() for item in self.metadata.model_names}

    def matches_pid(self, value: str) -> bool:
        """Return whether a product id matches this platform."""

        normalized = value.strip().lower()
        return normalized in {item.lower() for item in self.metadata.product_ids}

    def matches_platform_string(self, value: str) -> bool:
        """Return whether a platform string matches this platform."""

        normalized = value.strip().lower()
        return any(token.lower() in normalized for token in self.platform_strings)

    def matches_sys_object_id(self, value: str) -> bool:
        """Return whether a sysObjectID matches this platform."""

        normalized = value.strip()
        return normalized in self.sys_object_ids

    def matches_http_banner(self, value: str) -> bool:
        """Return whether an HTTP banner matches this platform."""

        normalized = value.strip().lower()
        return any(token.lower() in normalized for token in self.http_banners)
