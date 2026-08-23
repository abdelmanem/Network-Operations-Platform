"""Secret-provider factory and production adapter boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.app.transports.credentials import EnvironmentSecretProvider, SecretProvider
from backend.app.transports.secret_errors import ProviderConfigurationError

if TYPE_CHECKING:
    from backend.app.config.settings import Settings

_NON_PRODUCTION_ENVIRONMENTS = frozenset({"development", "test"})
_ENVIRONMENT_BACKEND = "environment"
_VAULT_BACKENDS = frozenset({"hashicorp_vault", "vault"})


def _normalized(value: str | None) -> str | None:
    cleaned = (value or "").strip().lower()
    return cleaned or None


def _is_non_production(app_env: str | None) -> bool:
    environment = _normalized(app_env) or "development"
    return environment in _NON_PRODUCTION_ENVIRONMENTS


@dataclass(slots=True)
class UnsupportedVaultSecretProvider:
    """Non-operational HashiCorp Vault adapter.

    This phase establishes the production provider name without shipping a
    working Vault client. Construction fails closed so production never
    silently uses environment variables.
    """

    def __post_init__(self) -> None:
        raise ProviderConfigurationError(
            "HashiCorp Vault secret provider is not implemented for this deployment."
        )

    def resolve_secret(self, _reference: str) -> str:
        raise ProviderConfigurationError(
            "HashiCorp Vault secret provider is not implemented for this deployment."
        )


def _unsupported_production_backend(backend: str) -> SecretProvider:
    if backend in _VAULT_BACKENDS:
        return UnsupportedVaultSecretProvider()
    raise ProviderConfigurationError(
        "SECRET_PROVIDER is not a supported production backend."
    )


def build_secret_provider(settings: Settings) -> SecretProvider:
    """Select a SecretProvider from deployment settings.

    Provider selection is independent of credential-profile provider_reference.
    """

    backend = _normalized(settings.secret_provider)
    if _is_non_production(settings.app_env):
        selected = backend or _ENVIRONMENT_BACKEND
        if selected == _ENVIRONMENT_BACKEND:
            return EnvironmentSecretProvider()
        return _unsupported_production_backend(selected)

    if backend is None:
        raise ProviderConfigurationError(
            "SECRET_PROVIDER is required outside development and test."
        )
    if backend == _ENVIRONMENT_BACKEND:
        raise ProviderConfigurationError(
            "The environment secret provider cannot be used outside "
            "development and test."
        )
    return _unsupported_production_backend(backend)
