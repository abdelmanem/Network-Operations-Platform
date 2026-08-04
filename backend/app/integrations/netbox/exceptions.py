"""NetBox integration exceptions."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.exceptions import ApplicationError


class NetBoxError(ApplicationError):
    """Base class for NetBox integration failures."""


class NetBoxConfigurationError(NetBoxError):
    """Raised when NetBox integration is misconfigured."""


class NetBoxAuthenticationError(NetBoxError):
    """Raised when authentication cannot be established."""


class NetBoxTransportError(NetBoxError):
    """Raised when the HTTP transport fails."""


class NetBoxCacheError(NetBoxError):
    """Raised when cache operations fail."""


class NetBoxValidationError(NetBoxError):
    """Raised when response validation fails."""


class NetBoxRateLimitError(NetBoxTransportError):
    """Raised when NetBox rate limits are exhausted."""


@dataclass(slots=True)
class NetBoxResponseError(NetBoxError):
    """Raised when NetBox returns an unexpected HTTP response."""

    status_code: int
    endpoint: str
    detail: str
    response_text: str | None = None

    def __str__(self) -> str:
        return f"{self.endpoint} returned {self.status_code}: {self.detail}"


@dataclass(slots=True)
class NetBoxVersionMismatchError(NetBoxValidationError):
    """Raised when the detected NetBox version does not match expectations."""

    expected_version: str
    actual_version: str

    def __str__(self) -> str:
        return f"Expected NetBox {self.expected_version}, got {self.actual_version}"
