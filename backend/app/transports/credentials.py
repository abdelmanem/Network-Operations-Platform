"""Credential resolution framework."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from backend.app.transports.secret_errors import (
    InvalidSecretReferenceError,
    ProviderConfigurationError,
    SecretNotFoundError,
)

if TYPE_CHECKING:
    from backend.app.transports.base import TransportContext


class TransportCredentials(Protocol):
    """Protocol for transport credentials."""

    def as_dict(self) -> dict[str, str]:
        """Return credentials in dictionary form."""


@dataclass(frozen=True, slots=True)
class UsernamePasswordCredentials:
    """Username/password credentials."""

    username: str
    password: str

    def as_dict(self) -> dict[str, str]:
        return {"username": self.username, "password": self.password}


@dataclass(frozen=True, slots=True)
class TokenCredentials:
    """Bearer/token credentials."""

    token: str
    scheme: str = "Bearer"

    def as_dict(self) -> dict[str, str]:
        return {"Authorization": f"{self.scheme} {self.token}"}


@dataclass(frozen=True, slots=True)
class SNMPv2cCredentials:
    """SNMPv2c community credentials."""

    community: str

    def as_dict(self) -> dict[str, str]:
        return {"community": self.community}


@dataclass(frozen=True, slots=True)
class SNMPv3Credentials:
    """SNMPv3 authentication and privacy credentials."""

    username: str
    security_level: str
    auth_protocol: str | None = None
    auth_secret: str | None = None
    privacy_protocol: str | None = None
    privacy_secret: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "username": self.username,
                "security_level": self.security_level,
                "auth_protocol": self.auth_protocol,
                "auth_secret": self.auth_secret,
                "privacy_protocol": self.privacy_protocol,
                "privacy_secret": self.privacy_secret,
            }.items()
            if value is not None
        }


class CredentialResolver(Protocol):
    """Protocol for resolving transport credentials."""

    def resolve(self, context: TransportContext) -> TransportCredentials | None:
        """Resolve credentials for a transport context."""


@dataclass(frozen=True, slots=True)
class CredentialReference:
    """Opaque tenant-scoped reference to a secret managed elsewhere."""

    credential_id: UUID | str
    transport: str
    tenant_id: str

    def as_dict(self) -> dict[str, str]:
        """Return non-secret reference metadata for diagnostics."""

        return {
            "credential_id": str(self.credential_id),
            "transport": self.transport,
            "tenant_id": self.tenant_id,
        }


class SecretProvider(Protocol):
    """Resolve a secret reference without exposing secret material in API DTOs."""

    def resolve_secret(self, reference: str) -> str:
        """Return a secret payload for the provided secret reference.

        Implementations must raise SecretProviderError subclasses and must never
        include secret material in exception messages.
        """


class CredentialProvider(Protocol):
    """Resolve an opaque reference only at execution time."""

    def resolve_reference(
        self, reference: CredentialReference
    ) -> TransportCredentials | None:
        """Return ephemeral credentials without persisting or serializing secrets."""


class CredentialResolutionError(RuntimeError):
    """Raised when a credential profile cannot produce safe runtime credentials."""


class CredentialProfile(Protocol):
    """Secret-free profile metadata required for runtime credential resolution."""

    id: UUID
    tenant_id: str
    provider_reference: str
    transport_types: list[str]
    credential_type: str | None
    username: str | None
    enabled: bool


ProfileLoader = Callable[[str, UUID], CredentialProfile | None]


@dataclass(slots=True)
class EnvironmentSecretProvider:
    """Process-environment secret provider for development and tests only."""

    prefix: str = "NOP_SECRET_"

    def resolve_secret(self, reference: str) -> str:
        if not self.prefix:
            raise ProviderConfigurationError(
                "Environment secret provider prefix is not configured."
            )
        cleaned = (reference or "").strip()
        if not cleaned:
            raise InvalidSecretReferenceError("Secret reference is invalid.")
        key = re.sub(r"[^A-Za-z0-9_\-]", "_", cleaned).upper()
        if not key.strip("_"):
            raise InvalidSecretReferenceError("Secret reference is invalid.")
        value = os.getenv(f"{self.prefix}{key}")
        if value is None:
            raise SecretNotFoundError("Requested secret was not found.")
        return value


@dataclass(slots=True)
class ProfileSecretCredentialProvider:
    """Build ephemeral transport credentials from a tenant-scoped profile secret."""

    secret_provider: SecretProvider
    profile_loader: ProfileLoader

    def resolve_reference(self, reference: CredentialReference) -> TransportCredentials:
        profile_id = self._profile_id(reference)
        profile = self.profile_loader(reference.tenant_id, profile_id)
        if profile is None or not profile.enabled:
            raise CredentialResolutionError("Credential profile was not found.")

        transport = self._transport_kind(reference.transport)
        if transport not in {item.strip().lower() for item in profile.transport_types}:
            raise CredentialResolutionError(
                "Credential profile does not support the selected transport."
            )

        credential_type = (profile.credential_type or "").strip().lower()
        if transport == "ssh":
            if credential_type not in {"ssh_password", "telnet_password"}:
                raise CredentialResolutionError(
                    "Credential profile is not compatible with SSH."
                )
            if not profile.username:
                raise CredentialResolutionError(
                    "Credential profile username is required for SSH."
                )
            return UsernamePasswordCredentials(
                username=profile.username,
                password=self.secret_provider.resolve_secret(
                    profile.provider_reference
                ),
            )
        if transport == "snmp":
            if credential_type != "snmp_v2c":
                raise CredentialResolutionError(
                    "Credential profile is not compatible with SNMP."
                )
            return SNMPv2cCredentials(
                community=self.secret_provider.resolve_secret(
                    profile.provider_reference
                )
            )
        if transport == "http":
            if credential_type == "http_basic":
                if not profile.username:
                    raise CredentialResolutionError(
                        "Credential profile username is required for HTTP basic auth."
                    )
                return UsernamePasswordCredentials(
                    username=profile.username,
                    password=self.secret_provider.resolve_secret(
                        profile.provider_reference
                    ),
                )
            if credential_type == "http_token":
                return TokenCredentials(
                    token=self.secret_provider.resolve_secret(
                        profile.provider_reference
                    )
                )

        raise CredentialResolutionError(
            "Credential profile is not compatible with the selected transport."
        )

    @staticmethod
    def _profile_id(reference: CredentialReference) -> UUID:
        try:
            return UUID(str(reference.credential_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise CredentialResolutionError(
                "Credential profile was not found."
            ) from exc

    @staticmethod
    def _transport_kind(transport: str) -> str:
        normalized = transport.strip().lower()
        aliases = {
            "ssh": "ssh",
            "paramiko": "ssh",
            "netmiko": "ssh",
            "snmp": "snmp",
            "snmpv2c": "snmp",
            "pysnmp": "snmp",
            "http": "http",
            "https": "http",
            "httpx": "http",
        }
        try:
            return aliases[normalized]
        except KeyError as exc:
            raise CredentialResolutionError(
                "Credential profile does not support the selected transport."
            ) from exc


@dataclass(slots=True)
class StaticCredentialResolver:
    """Return a fixed credential set."""

    credentials: TransportCredentials | None

    def resolve(self, context: TransportContext) -> TransportCredentials | None:
        return self.credentials


@dataclass(slots=True)
class MappingCredentialResolver:
    """Resolve credentials from a mapping keyed by target identifier."""

    credentials_by_target: dict[str, TransportCredentials]

    def resolve(self, context: TransportContext) -> TransportCredentials | None:
        return self.credentials_by_target.get(context.target.identifier)
