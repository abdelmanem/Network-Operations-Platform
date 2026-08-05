"""Collector execution exception hierarchy."""

from __future__ import annotations

from backend.app.core.exceptions import ApplicationError


class CollectorExecutionError(ApplicationError):
    """Base class for collector runtime failures."""


class CollectorNotFoundError(CollectorExecutionError):
    """Raised when no collector can satisfy a request."""


class TransportSelectionError(CollectorExecutionError):
    """Raised when no transport can satisfy a request."""


class CollectorExecutionStateError(CollectorExecutionError):
    """Raised when a job enters an invalid state transition."""


class CollectorExecutionCancelledError(CollectorExecutionError):
    """Raised when execution is cancelled."""


class CollectorExecutionTimeoutError(CollectorExecutionError):
    """Raised when execution exceeds the configured timeout."""


class CollectorRetryExhaustedError(CollectorExecutionError):
    """Raised when execution retries are exhausted."""
