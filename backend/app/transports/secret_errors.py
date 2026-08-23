"""Typed secret-provider failures that never include secret material."""

from __future__ import annotations

from backend.app.core.exceptions import ApplicationError


class SecretProviderError(ApplicationError):
    """Base class for secret-provider failures."""

    code: str = "provider_unavailable"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class SecretNotFoundError(SecretProviderError):
    """Raised when the referenced secret does not exist."""

    code = "secret_not_found"


class ProviderUnavailableError(SecretProviderError):
    """Raised when the secret backend cannot be reached."""

    code = "provider_unavailable"


class ProviderPermissionDeniedError(SecretProviderError):
    """Raised when the process is not allowed to read the secret."""

    code = "provider_permission_denied"


class InvalidSecretReferenceError(SecretProviderError):
    """Raised when the stored reference cannot be interpreted by this provider."""

    code = "invalid_reference"


class ProviderConfigurationError(SecretProviderError):
    """Raised when the secret provider itself is missing or invalid."""

    code = "provider_configuration_error"
