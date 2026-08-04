"""Credential resolution framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

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


class CredentialResolver(Protocol):
    """Protocol for resolving transport credentials."""

    def resolve(self, context: TransportContext) -> TransportCredentials | None:
        """Resolve credentials for a transport context."""


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
