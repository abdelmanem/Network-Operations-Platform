from backend.app.core.application import create_application
from fastapi.testclient import TestClient


def test_discovery_api_routes_are_registered_in_openapi() -> None:
    app = create_application()
    paths = app.openapi()["paths"]

    assert "/api/v1/discovery/targets" in paths
    assert "/api/v1/discovery/jobs" in paths
    assert "/api/v1/discovery/jobs/{job_id}" in paths
    assert "/api/v1/discovery/jobs/{job_id}/evidence" in paths


def test_discovery_root_is_available_without_authentication() -> None:
    with TestClient(create_application()) as client:
        response = client.get("/api/v1/discovery")

    assert response.status_code == 200
    assert response.json() == {"status": "available"}


def test_discovery_job_requires_authentication() -> None:
    with TestClient(create_application()) as client:
        response = client.get(
            "/api/v1/discovery/jobs",
            headers={"X-Tenant-ID": "tenant-a"},
        )

    assert response.status_code == 401
