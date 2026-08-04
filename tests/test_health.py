import pytest
from backend.app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.anyio
async def test_health_endpoint() -> None:
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
