"""Concrete HTTP transport implementation built on HTTPX."""

# ruff: noqa: ANN401

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.app.transports._support import (
    build_httpx_timeout,
    credential_headers,
    normalize_base_url,
    retry_async,
)
from backend.app.transports.base import TransportContext
from backend.app.transports.exceptions import (
    TransportConfigurationError,
    TransportHealthCheckError,
)
from backend.app.transports.http.base import HTTPTransport
from backend.app.transports.http.session import HTTPSession
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.session import TransportSession

logger = logging.getLogger(__name__)


def _httpx_module() -> Any:
    from backend.app.transports._support import import_optional

    return import_optional("httpx", "httpx")


@dataclass(slots=True, kw_only=True)
class HttpxHTTPSession(HTTPSession):
    """Manage an HTTPX client session."""

    base_url: str
    timeout: object
    retry_policy: TransportRetryPolicy | None = None
    headers: dict[str, str] = field(default_factory=dict)
    auth: object | None = None
    verify: bool | str = True
    follow_redirects: bool = True
    _client: Any | None = field(default=None, init=False, repr=False)

    @property
    def client(self) -> Any:
        """Return the underlying HTTPX client."""

        if self._client is None:
            raise RuntimeError("HTTPX session is not open.")
        return self._client

    async def open(self) -> None:
        """Open the HTTPX session."""

        if self.is_open:
            return

        httpx = _httpx_module()
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.headers,
            auth=self.auth,
            verify=self.verify,
            follow_redirects=self.follow_redirects,
        )
        await TransportSession.open(self)

    async def close(self) -> None:
        """Close the HTTPX session."""

        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self.closed_at is None:
            self.mark_closed()

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Execute a request with the configured retry policy."""

        self.ensure_open()
        retry_policy = kwargs.pop("retry_policy", self.retry_policy)

        async def operation() -> Any:
            response = await self.client.request(method, path, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                response.raise_for_status()
            return response

        return await retry_async(retry_policy, operation)


@dataclass(slots=True)
class HttpxTransport(HTTPTransport):
    """Concrete HTTP transport backed by HTTPX."""

    name: str = "httpx"
    verify: bool | str = True
    follow_redirects: bool = True
    default_headers: dict[str, str] = field(default_factory=dict)

    def health_check(self, context: TransportContext) -> None:
        """Validate HTTP transport configuration."""

        try:
            normalize_base_url(context.target.address)
        except TransportConfigurationError as exc:
            raise TransportHealthCheckError(str(exc)) from exc

    def create_session(self, context: TransportContext) -> HttpxHTTPSession:
        """Create an HTTPX session for the supplied target."""

        httpx = _httpx_module()
        base_url = normalize_base_url(context.target.address)
        headers = {**self.default_headers, **credential_headers(context.credentials)}
        auth: object | None = None
        if context.credentials is not None and "Authorization" not in headers:
            username = headers.pop("username", None)
            password = headers.pop("password", None)
            if username is not None or password is not None:
                auth = httpx.BasicAuth(username or "", password or "")

        timeout = build_httpx_timeout(context.timeout)
        session = HttpxHTTPSession(
            session_id=context.target.identifier,
            base_url=base_url,
            timeout=timeout,
            retry_policy=context.retry_policy,
            headers=headers,
            auth=auth,
            verify=self.verify,
            follow_redirects=self.follow_redirects,
        )
        logger.debug(
            "Prepared HTTPX session",
            extra={"target": context.target.identifier, "base_url": base_url},
        )
        return session

    def close(self) -> None:
        """Release transport-level resources."""
