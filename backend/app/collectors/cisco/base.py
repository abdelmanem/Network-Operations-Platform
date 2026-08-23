"""Cisco inventory collector base classes."""

# ruff: noqa: ANN401

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from backend.app.collectors.base import BaseCollector
from backend.app.collectors.cisco.inventory import CiscoInventoryParser
from backend.app.collectors.context import CollectorContext
from backend.app.discovery.context import DiscoveryTarget
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.context import ParserContext, ParserInputFormat
from backend.app.parsers.result import ParserResult
from backend.app.snapshot.entities import InventorySnapshot
from backend.app.transports.base import TransportCapability, TransportTarget
from backend.app.transports.credentials import CredentialReference
from backend.app.transports.manager import TransportManager
from backend.app.vendors.cisco.capabilities import CiscoCapability
from backend.app.vendors.cisco.catalog.commands import CommandCategory
from backend.app.vendors.cisco.catalog.snmp import SnmpGroup
from backend.app.vendors.cisco.detection import CiscoDetectionSignals
from backend.app.vendors.cisco.metadata import CiscoPlatformDefinition
from backend.app.vendors.cisco.platforms import CiscoPlatformRegistry, default_registry

logger = logging.getLogger(__name__)

TRANSPORT_PRIORITY: tuple[TransportCapability, ...] = (
    TransportCapability.SSH,
    TransportCapability.SNMP,
    TransportCapability.HTTP,
)
DEFAULT_TRANSPORT_NAMES: Mapping[TransportCapability, tuple[str, ...]] = {
    TransportCapability.SSH: ("netmiko", "paramiko"),
    TransportCapability.SNMP: ("pysnmp",),
    TransportCapability.HTTP: ("httpx",),
}
SSH_COMMAND_CATEGORIES: tuple[CommandCategory, ...] = (
    CommandCategory.INVENTORY,
    CommandCategory.SYSTEM,
    CommandCategory.INTERFACES,
    CommandCategory.VLANS,
    CommandCategory.POWER,
    CommandCategory.POE,
    CommandCategory.NEIGHBORS,
)
SNMP_GROUPS: tuple[SnmpGroup, ...] = (
    SnmpGroup.SYSTEM,
    SnmpGroup.INVENTORY,
    SnmpGroup.INTERFACES,
    SnmpGroup.VLANS,
    SnmpGroup.POE,
    SnmpGroup.NEIGHBORS,
)


class CiscoInventoryCollectionError(RuntimeError):
    """Raised when Cisco inventory collection cannot continue."""


@runtime_checkable
class CommandSession(Protocol):
    """Protocol for CLI-like transport sessions."""

    async def execute(self, command: str) -> str:
        """Execute one read-only command."""


@runtime_checkable
class SnmpWalkSession(Protocol):
    """Protocol for SNMP walk-capable sessions."""

    async def walk(self, oid: str) -> list[tuple[str, Any]]:
        """Walk one SNMP subtree."""


@runtime_checkable
class HttpRequestSession(Protocol):
    """Protocol for HTTP request-capable sessions."""

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Request one HTTP endpoint."""


@dataclass(frozen=True, slots=True)
class CiscoTransportSelection:
    """Selected Cisco transport metadata."""

    capability: TransportCapability
    transport_name: str


@dataclass(slots=True)
class CiscoTransportSelector:
    """Resolve the best available transport for a Cisco platform."""

    transport_manager: TransportManager
    transport_names: Mapping[TransportCapability, tuple[str, ...]] = field(
        default_factory=lambda: DEFAULT_TRANSPORT_NAMES
    )

    def select(
        self,
        platform: CiscoPlatformDefinition,
        *,
        preferred_transport_name: str | None = None,
    ) -> CiscoTransportSelection:
        """Select SSH, SNMP, then HTTP according to platform support."""

        if preferred_transport_name is not None:
            transport = self.transport_manager.resolve(preferred_transport_name)
            capabilities = platform.metadata.transport_support & transport.capabilities
            if not capabilities:
                raise CiscoInventoryCollectionError(
                    f"Transport {preferred_transport_name!r} is not supported by "
                    f"{platform.family!r}."
                )
            return CiscoTransportSelection(
                capability=self._highest_priority(capabilities),
                transport_name=transport.name,
            )

        for capability in TRANSPORT_PRIORITY:
            if capability not in platform.metadata.transport_support:
                continue
            for name in self.transport_names.get(capability, ()):
                try:
                    transport = self.transport_manager.resolve(name)
                except KeyError:
                    continue
                if capability in transport.capabilities:
                    return CiscoTransportSelection(
                        capability=capability,
                        transport_name=transport.name,
                    )

        raise CiscoInventoryCollectionError(
            f"No registered transport is available for {platform.family!r}."
        )

    @staticmethod
    def _highest_priority(
        capabilities: Iterable[TransportCapability],
    ) -> TransportCapability:
        capability_set = frozenset(capabilities)
        for capability in TRANSPORT_PRIORITY:
            if capability in capability_set:
                return capability
        raise CiscoInventoryCollectionError("No supported transport capability found.")


@dataclass(slots=True, kw_only=True)
class CiscoInventoryCollectorBase(BaseCollector):
    """Base implementation for Cisco inventory collectors."""

    platform_family: str
    transport_manager: TransportManager
    platform_registry: CiscoPlatformRegistry = field(default_factory=default_registry)
    parser: CiscoInventoryParser = field(default_factory=CiscoInventoryParser)
    normalization_engine: NormalizationEngine = field(
        default_factory=NormalizationEngine
    )
    selector: CiscoTransportSelector | None = None

    def __post_init__(self) -> None:
        if self.selector is None:
            self.selector = CiscoTransportSelector(self.transport_manager)

    async def health_check(self, context: CollectorContext) -> None:
        """Validate that a supported Cisco platform can be resolved."""

        self.resolve_platform(context)

    async def discover(self, context: CollectorContext) -> tuple[DiscoveryTarget, ...]:
        """Cisco inventory collectors do not discover downstream targets."""

        return ()

    async def collect(
        self,
        context: CollectorContext,
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> dict[str, object]:
        """Collect raw Cisco inventory data through the selected transport."""

        platform = self.resolve_platform(context)
        selection = self.select_transport(context, platform)
        target = TransportTarget(
            identifier=context.target.identifier,
            address=context.target.address,
            metadata=dict(context.target.metadata),
            credential_reference=self._credential_reference(
                context, selection.transport_name
            ),
        )
        session = await self.transport_manager.open_session(
            selection.transport_name,
            target,
            capabilities=frozenset({selection.capability}),
        )
        logger.info(
            "Collecting Cisco inventory",
            extra={
                "target": context.target.identifier,
                "platform_family": platform.family,
                "transport": selection.transport_name,
            },
        )

        payload: dict[str, object] = {
            "target": {
                "identifier": context.target.identifier,
                "address": context.target.address,
                "metadata": dict(context.target.metadata),
            },
            "platform_family": platform.family,
            "parser_family": platform.metadata.parser_family,
            "transport": selection.transport_name,
            "transport_capability": selection.capability.value,
        }
        if selection.capability == TransportCapability.SSH:
            payload["commands"] = await self._collect_ssh(platform, session)
        elif selection.capability == TransportCapability.SNMP:
            payload["snmp"] = await self._collect_snmp(platform, session)
        elif selection.capability == TransportCapability.HTTP:
            payload["http"] = await self._collect_http(platform, session)
        else:  # pragma: no cover - defensive guard for future enum values
            raise CiscoInventoryCollectionError(
                f"Unsupported transport capability: {selection.capability}"
            )
        return payload

    @staticmethod
    def _credential_reference(
        context: CollectorContext, transport: str
    ) -> CredentialReference | None:
        reference = context.target.metadata.get("credential_profile_id")
        if reference is None:
            reference = context.target.metadata.get("credential_reference")
        tenant_id = context.target.tenant_id
        if reference is None or tenant_id is None:
            return None
        return CredentialReference(
            credential_id=str(reference),
            transport=transport,
            tenant_id=tenant_id,
        )

    async def normalize(
        self,
        context: CollectorContext,
        raw_payload: dict[str, object],
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> InventorySnapshot:
        """Normalize raw Cisco inventory into a canonical snapshot."""

        parser_context = ParserContext(
            source=context.target.identifier,
            input_format=ParserInputFormat.JSON,
            parser_name=self.parser.name,
            run_id=context.run_id,
            metadata=dict(context.metadata),
        )
        parsed = self.parser.parse(parser_context, raw_payload)
        normalized = self.normalization_engine.normalize(parsed)
        return normalized.snapshot

    async def close(self) -> None:
        """Release pooled transport sessions owned by the manager."""

        await self.transport_manager.close_all()

    def resolve_platform(self, context: CollectorContext) -> CiscoPlatformDefinition:
        """Resolve platform metadata from collector configuration and target hints."""

        family = self._optional_string(context.target.metadata.get("platform_family"))
        if family is None:
            family = self._optional_string(context.metadata.get("platform_family"))
        if family is None:
            family = self.platform_family
        if family:
            family = self.platform_registry.canonicalize_family(family)
            try:
                return self.platform_registry.get(family)
            except KeyError:
                pass

        platform = self.platform_registry.detect(
            CiscoDetectionSignals(
                model=self._optional_string(context.target.metadata.get("model")),
                product_id=self._optional_string(
                    context.target.metadata.get("product_id")
                ),
                platform_string=self._optional_string(
                    context.target.metadata.get("platform_string")
                ),
                sys_object_id=self._optional_string(
                    context.target.metadata.get("sys_object_id")
                ),
                http_banner=self._optional_string(
                    context.target.metadata.get("http_banner")
                ),
            )
        )
        if platform is None:
            raise CiscoInventoryCollectionError(
                "Unable to resolve supported Cisco platform."
            )
        return platform

    def select_transport(
        self,
        context: CollectorContext,
        platform: CiscoPlatformDefinition,
    ) -> CiscoTransportSelection:
        """Select the best registered transport for this platform."""

        preferred = self._optional_string(context.metadata.get("transport_name"))
        if self.selector is None:  # pragma: no cover - protected by __post_init__
            raise CiscoInventoryCollectionError("Cisco transport selector is missing.")
        return self.selector.select(platform, preferred_transport_name=preferred)

    async def _collect_ssh(
        self,
        platform: CiscoPlatformDefinition,
        session: object,
    ) -> dict[str, str]:
        if not isinstance(session, CommandSession):
            raise CiscoInventoryCollectionError("Selected SSH session cannot execute.")

        commands: dict[str, str] = {}
        for command in self._inventory_commands(platform):
            if command in commands:
                continue
            commands[command] = await session.execute(command)
        return commands

    async def _collect_snmp(
        self,
        platform: CiscoPlatformDefinition,
        session: object,
    ) -> dict[str, list[tuple[str, str]]]:
        if not isinstance(session, SnmpWalkSession):
            raise CiscoInventoryCollectionError("Selected SNMP session cannot walk.")

        results: dict[str, list[tuple[str, str]]] = {}
        for group in SNMP_GROUPS:
            if not self._snmp_group_supported(platform, group):
                continue
            rows: list[tuple[str, str]] = []
            for oid in platform.snmp_catalog.oids(group):
                walk_rows = await session.walk(oid)
                rows.extend((name, str(value)) for name, value in walk_rows)
            if rows:
                results[group.value] = rows
        return results

    async def _collect_http(
        self,
        platform: CiscoPlatformDefinition,
        session: object,
    ) -> dict[str, str]:
        if not isinstance(session, HttpRequestSession):
            raise CiscoInventoryCollectionError("Selected HTTP session cannot request.")

        responses: dict[str, str] = {}
        for endpoint in platform.http_catalog.endpoints:
            response = await session.request(endpoint.method.value, endpoint.path)
            responses[endpoint.path] = await self._response_text(response)
        return responses

    def _inventory_commands(self, platform: CiscoPlatformDefinition) -> tuple[str, ...]:
        commands: list[str] = []
        for category in SSH_COMMAND_CATEGORIES:
            if category in {CommandCategory.POWER, CommandCategory.POE}:
                if CiscoCapability.POE not in platform.metadata.capabilities:
                    continue
            for definition in platform.command_catalog.commands(category):
                if "running-config" in definition.command:
                    continue
                if "startup-config" in definition.command:
                    continue
                commands.append(definition.command)
        return tuple(dict.fromkeys(commands))

    @staticmethod
    def _snmp_group_supported(
        platform: CiscoPlatformDefinition,
        group: SnmpGroup,
    ) -> bool:
        if group == SnmpGroup.POE:
            return CiscoCapability.POE in platform.metadata.capabilities
        if group == SnmpGroup.VLANS:
            return CiscoCapability.VLAN in platform.metadata.capabilities
        if group == SnmpGroup.NEIGHBORS:
            return CiscoCapability.NEIGHBOR_DISCOVERY in platform.metadata.capabilities
        return True

    @staticmethod
    async def _response_text(response: object) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        aread = getattr(response, "aread", None)
        if callable(aread):
            data = await aread()
            if isinstance(data, bytes):
                return data.decode(errors="replace")
        return str(response)

    @staticmethod
    def _optional_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None


def parse_cisco_inventory_payload(
    parser: CiscoInventoryParser,
    context: CollectorContext,
    raw_payload: dict[str, object],
) -> ParserResult:
    """Parse Cisco inventory payloads with standard parser context."""

    parser_context = ParserContext(
        source=context.target.identifier,
        input_format=ParserInputFormat.JSON,
        parser_name=parser.name,
        run_id=context.run_id,
        metadata=dict(context.metadata),
    )
    return parser.parse(parser_context, raw_payload)
