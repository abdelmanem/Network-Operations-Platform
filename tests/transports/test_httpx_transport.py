"""Tests for the concrete HTTPX transport."""

# ruff: noqa: S105

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from backend.app.transports import (
    HttpxHTTPSession,
    HttpxTransport,
    TransportContext,
    TransportRetryPolicy,
    TransportTarget,
)
from backend.app.transports.credentials import TokenCredentials

HTTP_TOKEN = "abc123"


class _FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        raise RuntimeError("HTTP error")


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.failures = 0

    async def request(self, method: str, path: str, **kwargs: object) -> _FakeResponse:
        self.calls.append((method, path))
        if self.failures < 1:
            self.failures += 1
            raise ConnectionError("temporary failure")
        return _FakeResponse()

    async def aclose(self) -> None:
        return None


def test_httpx_transport_creates_session_with_headers() -> None:
    transport = HttpxTransport()
    context = TransportContext(
        target=TransportTarget(
            identifier="edge-1",
            address="https://api.example.invalid",
        ),
        credentials=TokenCredentials(token=HTTP_TOKEN),
    )

    session = transport.create_session(context)

    assert session.base_url == "https://api.example.invalid"
    assert session.headers["Authorization"] == "Bearer abc123"


def test_httpx_session_request_retries_transient_failure() -> None:
    session = HttpxHTTPSession(
        session_id="edge-1",
        base_url="https://api.example.invalid",
        timeout=object(),
        retry_policy=TransportRetryPolicy(max_attempts=2),
    )
    session._client = _FakeClient()
    session.opened_at = datetime.now(UTC)
    session.closed_at = None

    async def run() -> None:
        response = await session.request("GET", "/health")
        assert response.status_code == 200

    asyncio.run(run())
