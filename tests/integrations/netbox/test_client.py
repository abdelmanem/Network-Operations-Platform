import httpx
import pytest
from backend.app.integrations.netbox.client import NetBoxClient
from backend.app.integrations.netbox.exceptions import NetBoxVersionMismatchError


@pytest.mark.anyio
async def test_client_retries_on_transient_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(
        "backend.app.integrations.netbox.client.asyncio.sleep", fake_sleep
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(503, request=request, json={"detail": "busy"})
        return httpx.Response(
            200,
            request=request,
            headers={"API-Version": "4.6.7"},
            json={"version": "4.6.7", "status": "ok"},
        )

    client = NetBoxClient(
        base_url="https://netbox.example.com",
        authentication=None,
        expected_version="4.6.7",
        transport=httpx.MockTransport(handler),
    )

    try:
        health = await client.health()
    finally:
        await client.aclose()

    assert health.version == "4.6.7"
    assert calls["count"] == 3
    assert len(sleeps) == 2


@pytest.mark.anyio
async def test_client_honors_retry_after_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(
        "backend.app.integrations.netbox.client.asyncio.sleep", fake_sleep
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                429,
                request=request,
                headers={"Retry-After": "1.25"},
                json={"detail": "rate limited"},
            )
        return httpx.Response(
            200,
            request=request,
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{"id": 1, "name": "Site A", "slug": "site-a"}],
            },
        )

    client = NetBoxClient(
        base_url="https://netbox.example.com",
        authentication=None,
        transport=httpx.MockTransport(handler),
    )

    try:
        page = await client.fetch_page("/api/dcim/sites/")
    finally:
        await client.aclose()

    assert page.count == 1
    assert calls["count"] == 2
    assert sleeps[0] == pytest.approx(1.25)


@pytest.mark.anyio
async def test_client_raises_on_version_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"API-Version": "4.6.7"},
            json={"version": "4.6.6", "status": "ok"},
        )

    client = NetBoxClient(
        base_url="https://netbox.example.com",
        authentication=None,
        expected_version="4.6.7",
        transport=httpx.MockTransport(handler),
    )

    try:
        with pytest.raises(NetBoxVersionMismatchError):
            await client.health()
    finally:
        await client.aclose()
