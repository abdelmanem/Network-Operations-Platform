"""Transport framework exceptions."""

from __future__ import annotations


class TransportError(RuntimeError):
    """Base class for transport failures."""


class TransportDependencyError(TransportError):
    """Raised when a required transport dependency is unavailable."""


class TransportConfigurationError(TransportError):
    """Raised when transport configuration is invalid."""


class TransportConnectionError(TransportError):
    """Raised when a transport cannot connect."""


class TransportAuthenticationError(TransportError):
    """Raised when a device rejects transport authentication."""


class TransportUnavailableError(TransportError):
    """Raised when a requested transport is not registered or available."""


class TransportHealthCheckError(TransportError):
    """Raised when a transport health check fails."""
