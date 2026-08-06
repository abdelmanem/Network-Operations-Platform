"""Internal helpers for concrete transport adapters."""

# ruff: noqa: ANN401,UP047

from __future__ import annotations

import asyncio
import importlib
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

from backend.app.transports.credentials import (
    TokenCredentials,
    TransportCredentials,
    UsernamePasswordCredentials,
)
from backend.app.transports.exceptions import (
    TransportConfigurationError,
    TransportDependencyError,
)
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.timeout import TransportTimeout


def import_optional(module_name: str, dependency_name: str) -> Any:
    """Import an optional dependency or raise a transport error."""

    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency missing
        raise TransportDependencyError(
            f"Optional transport dependency '{dependency_name}' is not installed."
        ) from exc


def build_httpx_timeout(timeout: TransportTimeout | None) -> object:
    """Build an HTTPX timeout object lazily."""

    httpx = import_optional("httpx", "httpx")
    if timeout is None:
        return httpx.Timeout(timeout=30.0)
    return httpx.Timeout(
        timeout=timeout.total_seconds if timeout.total_seconds is not None else 30.0,
        connect=timeout.connect_seconds,
        read=timeout.read_seconds,
        write=timeout.write_seconds,
        pool=timeout.total_seconds,
    )


def normalize_base_url(address: str) -> str:
    """Normalize a base URL for HTTP transports."""

    parsed = urlparse(address)
    if parsed.scheme:
        return address.rstrip("/")
    if not address:
        raise TransportConfigurationError("HTTP target address is required.")
    return f"https://{address}".rstrip("/")


def extract_username_password(
    credentials: TransportCredentials | None,
) -> tuple[str | None, str | None]:
    """Extract username/password credentials when available."""

    if isinstance(credentials, UsernamePasswordCredentials):
        return credentials.username, credentials.password
    if isinstance(credentials, TokenCredentials):
        return credentials.token, None
    return None, None


def credential_headers(
    credentials: TransportCredentials | None,
) -> dict[str, str]:
    """Return HTTP headers derived from credentials."""

    if credentials is None:
        return {}
    return credentials.as_dict()


def metadata_string(
    metadata: dict[str, object],
    key: str,
    default: str,
) -> str:
    """Return a string metadata value."""

    value = metadata.get(key, default)
    if isinstance(value, str):
        return value
    raise TransportConfigurationError(f"Metadata value '{key}' must be a string.")


def metadata_optional_string(
    metadata: dict[str, object],
    key: str,
) -> str | None:
    """Return an optional string metadata value."""

    value = metadata.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise TransportConfigurationError(
        f"Metadata value '{key}' must be a string when provided."
    )


def metadata_int(
    metadata: dict[str, object],
    key: str,
    default: int,
) -> int:
    """Return an integer metadata value."""

    value = metadata.get(key, default)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TransportConfigurationError(f"Metadata value '{key}' must be an integer.")


async def retry_async[
    T
](policy: TransportRetryPolicy | None, operation: Callable[[], Awaitable[T]],) -> T:
    """Execute an async operation with retry policy support."""

    if policy is None:
        return await operation()

    last_error: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await operation()
        except BaseException as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= policy.max_attempts or not policy.should_retry_exception(exc):
                raise
            await asyncio.sleep(policy.delay_for_attempt(attempt))
    raise TransportConfigurationError("Retry loop exhausted.") from last_error


def retry_sync[T](policy: TransportRetryPolicy | None, operation: Callable[[], T]) -> T:
    """Execute a sync operation with retry policy support."""

    if policy is None:
        return operation()

    last_error: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return operation()
        except BaseException as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= policy.max_attempts or not policy.should_retry_exception(exc):
                raise
            time.sleep(policy.delay_for_attempt(attempt))
    raise TransportConfigurationError("Retry loop exhausted.") from last_error
