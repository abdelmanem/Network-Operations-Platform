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


class TransportHealthCheckError(TransportError):
    """Raised when a transport health check fails."""
