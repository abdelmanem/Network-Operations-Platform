"""Credential resolution framework."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

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

    def resolve_secret(self, reference: str) -> str | None:
        """Return a secret payload for the provided secret reference."""


class CredentialProvider(Protocol):
    """Resolve an opaque reference only at execution time."""

    def resolve_reference(
        self, reference: CredentialReference
    ) -> TransportCredentials | None:
        """Return ephemeral credentials without persisting or serializing secrets."""


@dataclass(slots=True)
class EnvironmentSecretProvider:
    """Minimal secret provider for local and test environments."""

    prefix: str = "NOP_SECRET_"

    def resolve_secret(self, reference: str) -> str | None:
        key = re.sub(r"[^A-Za-z0-9_\-]", "_", reference).upper()
        return os.getenv(f"{self.prefix}{key}")


@dataclass(slots=True)
class EnvironmentCredentialProvider:
    """Resolve opaque profile IDs from environment variables at execution time."""

    prefix: str = "NOP_CREDENTIAL_"

    def resolve_reference(
        self, reference: CredentialReference
    ) -> TransportCredentials | None:
        key = re.sub(r"[^A-Za-z0-9]", "_", str(reference.credential_id)).upper()
        transport = reference.transport.upper().replace("-", "_")
        value = os.getenv(f"{self.prefix}{key}_{transport}")
        if value is None:
            return None
        if transport in {"SNMP", "SNMPV2C"}:
            return SNMPv2cCredentials(community=value)
        username = os.getenv(f"{self.prefix}{key}_USERNAME")
        if username is None:
            return None
        return UsernamePasswordCredentials(username=username, password=value)


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
