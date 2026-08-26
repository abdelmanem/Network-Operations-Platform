"""Multi-transport discovery policy configuration and resolution.

This module provides the policy configuration and resolution mechanisms for
multi-transport discovery. It extends existing credential profile and discovery
target models to support explicit transport priority ordering and fallback chains.

Key features:
- Explicit transport priority ordering (not implicit defaults)
- Per-transport credential compatibility checking
- Security controls for insecure transports (Telnet)
- Policy resolution from credential profiles and discovery targets
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.app.discovery.probing import TransportService
from backend.app.transports.base import TransportCapability

if TYPE_CHECKING:
    from backend.app.persistence.models import CredentialProfileRecord


# Default transport priority for Cisco network discovery
# This ordering prioritizes secure transports and common Cisco management interfaces
DEFAULT_TRANSPORT_PRIORITY: tuple[TransportCapability, ...] = (
    TransportCapability.SSH,
    TransportCapability.TELNET,
    TransportCapability.HTTPS,
    TransportCapability.HTTP,
    TransportCapability.SNMP,
)

# Mapping of transport capabilities to their service counterparts
CAPABILITY_TO_SERVICE: dict[TransportCapability, TransportService] = {
    TransportCapability.SSH: TransportService.SSH,
    TransportCapability.TELNET: TransportService.TELNET,
    TransportCapability.HTTP: TransportService.HTTP,
    TransportCapability.HTTPS: TransportService.HTTPS,
    TransportCapability.SNMP: TransportService.SNMP,
}

# Transports considered insecure and requiring explicit opt-in
INSECURE_TRANSPORTS: frozenset[TransportCapability] = frozenset({TransportCapability.TELNET})

# Credential type compatibility mapping
# Defines which credential types can be used with which transports
CREDENTIAL_TYPE_COMPATIBILITY: dict[str, list[str]] = {
    "ssh_password": ["ssh", "telnet"],
    "ssh_key": ["ssh"],
    "telnet_password": ["telnet"],
    "snmp_v2c": ["snmp"],
    "snmp_v3": ["snmp"],
    "http_basic": ["http", "https"],
    "http_token": ["http", "https"],
}


@dataclass(frozen=True, slots=True)
class TransportPolicyEntry:
    """Configuration for a single transport in the policy chain."""

    capability: TransportCapability
    transport_name: str
    service: TransportService
    is_insecure: bool = False
    credential_compatible: bool = True


@dataclass(frozen=True, slots=True)
class MultiTransportPolicy:
    """Explicit ordered transport policy for multi-transport discovery.

    This class represents a complete transport policy including:
    - Explicit priority ordering of transports
    - Security controls for insecure transports
    - Credential compatibility validation

    The policy is constructed from credential profiles and discovery targets,
    ensuring that only explicitly configured and authorized transports are used.
    """

    transports: tuple[TransportPolicyEntry, ...]
    allow_insecure: bool = False
    credential_profile_id: str | None = None

    def __post_init__(self) -> None:
        """Validate that insecure transports are only used when explicitly allowed."""
        if not self.allow_insecure:
            insecure_in_policy = [
                t for t in self.transports if t.is_insecure
            ]
            if insecure_in_policy:
                raise ValueError(
                    f"Insecure transports require explicit allow_insecure=True: "
                    f"{[t.transport_name for t in insecure_in_policy]}"
                )

    @property
    def transport_names(self) -> list[str]:
        """Return list of transport names in priority order."""
        return [t.transport_name for t in self.transports]

    @property
    def has_insecure_transport(self) -> bool:
        """Return True if the policy includes any insecure transports."""
        return any(t.is_insecure for t in self.transports)

    @property
    def is_empty(self) -> bool:
        """Return True if the policy contains no transports."""
        return len(self.transports) == 0

    def get_compatible_transports(
        self, credential_type: str | None
    ) -> list[TransportPolicyEntry]:
        """Filter transports by credential type compatibility.

        Args:
            credential_type: The credential type to check compatibility for

        Returns:
            List of transports compatible with the credential type
        """
        if not credential_type:
            return list(self.transports)

        compatible = CREDENTIAL_TYPE_COMPATIBILITY.get(credential_type, [])

        return [
            t
            for t in self.transports
            if t.transport_name in compatible
        ]

    @classmethod
    def from_credential_profile(
        cls,
        profile: CredentialProfileRecord,
        *,
        allow_insecure: bool = False,
    ) -> MultiTransportPolicy:
        """Construct a transport policy from a credential profile.

        The credential profile's transport_types field defines which transports
        are available and their priority order.

        Args:
            profile: The credential profile to build policy from
            allow_insecure: Whether to allow insecure transports like Telnet

        Returns:
            MultiTransportPolicy configured according to the profile
        """
        transport_types = profile.transport_types or []
        credential_type = profile.credential_type

        if not transport_types:
            # Default to SSH if no transports specified (backward compatibility)
            transport_types = ["ssh"]

        transports: list[TransportPolicyEntry] = []

        for transport_name in transport_types:
            transport_lower = transport_name.lower()

            # Map transport name to capability
            try:
                capability = TransportCapability(transport_name.upper())
            except ValueError:
                # Skip unknown transport types
                continue

            # Get corresponding service
            service = CAPABILITY_TO_SERVICE.get(capability)
            if not service:
                continue

            # Check if transport is insecure
            is_insecure = capability in INSECURE_TRANSPORTS

            # Check credential compatibility
            credential_compatible = True
            if credential_type:
                compatible_transports = CREDENTIAL_TYPE_COMPATIBILITY.get(
                    credential_type, []
                )
                credential_compatible = transport_lower in compatible_transports

            entry = TransportPolicyEntry(
                capability=capability,
                transport_name=transport_lower,
                service=service,
                is_insecure=is_insecure,
                credential_compatible=credential_compatible,
            )
            transports.append(entry)

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_transports: list[TransportPolicyEntry] = []
        for t in transports:
            if t.transport_name not in seen:
                seen.add(t.transport_name)
                unique_transports.append(t)

        return cls(
            transports=tuple(unique_transports),
            allow_insecure=allow_insecure,
            credential_profile_id=str(profile.id) if profile.id else None,
        )


__all__ = [
    "MultiTransportPolicy",
    "TransportPolicyEntry",
    "DEFAULT_TRANSPORT_PRIORITY",
    "INSECURE_TRANSPORTS",
    "CAPABILITY_TO_SERVICE",
    "CREDENTIAL_TYPE_COMPATIBILITY",
]