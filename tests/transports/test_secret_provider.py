from types import SimpleNamespace

import pytest
from backend.app.transports.credentials import EnvironmentSecretProvider
from backend.app.transports.secret_errors import (
    InvalidSecretReferenceError,
    ProviderConfigurationError,
    ProviderPermissionDeniedError,
    ProviderUnavailableError,
    SecretNotFoundError,
    SecretProviderError,
)
from backend.app.transports.secret_provider import (
    UnsupportedVaultSecretProvider,
    build_secret_provider,
)

_SECRET_VALUE = "runtime-secret-must-never-leak"


def test_environment_provider_lookup_uses_sanitized_prefix(monkeypatch) -> None:
    monkeypatch.setenv("NOP_SECRET_RADISSON", _SECRET_VALUE)
    provider = EnvironmentSecretProvider()

    assert provider.resolve_secret("Radisson") == _SECRET_VALUE
    assert provider.resolve_secret("radisson") == _SECRET_VALUE


def test_environment_provider_missing_secret_raises_typed_error() -> None:
    provider = EnvironmentSecretProvider()

    with pytest.raises(SecretNotFoundError) as excinfo:
        provider.resolve_secret("missing-reference")

    assert excinfo.value.code == "secret_not_found"
    assert _SECRET_VALUE not in str(excinfo.value)
    assert "missing-reference" not in str(excinfo.value)


def test_environment_provider_invalid_reference_raises_typed_error() -> None:
    provider = EnvironmentSecretProvider()

    with pytest.raises(InvalidSecretReferenceError) as excinfo:
        provider.resolve_secret("   ")

    assert excinfo.value.code == "invalid_reference"
    assert "   " not in repr(excinfo.value)


def test_environment_provider_punctuation_only_reference_is_invalid() -> None:
    provider = EnvironmentSecretProvider()

    with pytest.raises(InvalidSecretReferenceError) as excinfo:
        provider.resolve_secret("!!!")

    assert excinfo.value.code == "invalid_reference"
    assert "!!!" not in str(excinfo.value)


def test_secret_provider_error_codes_are_stable() -> None:
    assert SecretNotFoundError("x").code == "secret_not_found"
    assert ProviderUnavailableError("x").code == "provider_unavailable"
    assert ProviderPermissionDeniedError("x").code == "provider_permission_denied"
    assert InvalidSecretReferenceError("x").code == "invalid_reference"
    assert ProviderConfigurationError("x").code == "provider_configuration_error"
    assert issubclass(SecretNotFoundError, SecretProviderError)


def test_factory_defaults_to_environment_in_development() -> None:
    provider = build_secret_provider(
        SimpleNamespace(app_env="development", secret_provider=None)
    )
    assert isinstance(provider, EnvironmentSecretProvider)


def test_factory_defaults_to_environment_in_test() -> None:
    provider = build_secret_provider(
        SimpleNamespace(app_env="test", secret_provider=None)
    )
    assert isinstance(provider, EnvironmentSecretProvider)


def test_factory_honors_explicit_environment_backend_in_development() -> None:
    provider = build_secret_provider(
        SimpleNamespace(app_env="development", secret_provider="environment")
    )
    assert isinstance(provider, EnvironmentSecretProvider)


def test_production_requires_explicit_non_environment_provider() -> None:
    with pytest.raises(ProviderConfigurationError) as excinfo:
        build_secret_provider(
            SimpleNamespace(app_env="production", secret_provider=None)
        )

    assert excinfo.value.code == "provider_configuration_error"
    assert isinstance(excinfo.value, SecretProviderError)


def test_production_refuses_environment_provider() -> None:
    with pytest.raises(ProviderConfigurationError) as excinfo:
        build_secret_provider(
            SimpleNamespace(app_env="production", secret_provider="environment")
        )

    assert excinfo.value.code == "provider_configuration_error"


def test_production_vault_selection_fails_closed_without_fallback() -> None:
    with pytest.raises(ProviderConfigurationError) as excinfo:
        build_secret_provider(
            SimpleNamespace(app_env="production", secret_provider="hashicorp_vault")
        )

    assert excinfo.value.code == "provider_configuration_error"
    assert _SECRET_VALUE not in str(excinfo.value)


def test_unsupported_vault_adapter_never_resolves_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("NOP_SECRET_RADISSON", _SECRET_VALUE)

    with pytest.raises(ProviderConfigurationError) as excinfo:
        UnsupportedVaultSecretProvider()

    assert excinfo.value.code == "provider_configuration_error"
    assert _SECRET_VALUE not in str(excinfo.value)


def test_unknown_production_backend_fails_configuration() -> None:
    with pytest.raises(ProviderConfigurationError) as excinfo:
        build_secret_provider(
            SimpleNamespace(app_env="production", secret_provider="not-a-backend")
        )

    assert excinfo.value.code == "provider_configuration_error"
