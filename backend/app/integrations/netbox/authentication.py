"""NetBox authentication strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class NetBoxAuthentication(Protocol):
    """Protocol for NetBox authentication strategies."""

    def build_headers(self) -> dict[str, str]:
        """Return HTTP headers required for authentication."""


@dataclass(frozen=True, slots=True)
class TokenAuthentication:
    """Token-based authentication for NetBox."""

    token: str

    def build_headers(self) -> dict[str, str]:
        """Return HTTP headers required for token authentication."""

        return {"Authorization": f"Bearer {self.token}"}


@dataclass(frozen=True, slots=True)
class OAuthAuthentication:
    """OAuth-compatible authentication strategy."""

    access_token: str
    scheme: str = "Bearer"

    def build_headers(self) -> dict[str, str]:
        """Return HTTP headers required for OAuth authentication."""

        return {"Authorization": f"{self.scheme} {self.access_token}"}


def build_authentication(
    *,
    token: str | None = None,
    access_token: str | None = None,
    scheme: str = "Bearer",
) -> NetBoxAuthentication | None:
    """Build an authentication strategy from configured secrets."""

    if access_token:
        return OAuthAuthentication(access_token=access_token, scheme=scheme)
    if token:
        return TokenAuthentication(token=token)
    return None
