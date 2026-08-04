"""Application exception hierarchy."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base class for all application-level exceptions."""


class ConfigurationError(ApplicationError):
    """Raised when configuration cannot be loaded."""


class LifecycleError(ApplicationError):
    """Raised when application startup or shutdown fails."""


class DependencyError(ApplicationError):
    """Raised when dependency injection cannot resolve a dependency."""


class PluginError(ApplicationError):
    """Raised when plugin registration or lookup fails."""


class DomainError(ApplicationError):
    """Raised when a domain invariant is violated."""


class RepositoryError(ApplicationError):
    """Raised when repository operations fail."""


class TransactionError(ApplicationError):
    """Raised when transactional boundaries fail."""


class ServiceError(ApplicationError):
    """Raised when a service operation fails."""


class EventError(ApplicationError):
    """Raised when event dispatch or handling fails."""
