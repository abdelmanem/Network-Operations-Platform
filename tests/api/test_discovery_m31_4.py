from datetime import UTC, datetime
from uuid import uuid4

from backend.app.api.v1.discovery import get_job_devices
from backend.app.core.application import create_application
from backend.app.models.base import BaseModel
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
    SnapshotDeviceRecord,
    SnapshotRecord,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_discovery_api_routes_are_registered_in_openapi() -> None:
    app = create_application()
    paths = app.openapi()["paths"]

    assert "/api/v1/discovery/targets" in paths
    assert "/api/v1/discovery/jobs" in paths
    assert "/api/v1/discovery/jobs/{job_id}" in paths
    assert "/api/v1/discovery/jobs/{job_id}/evidence" in paths
    assert "post" in paths["/api/v1/comparison"]


def test_discovery_root_is_available_without_authentication() -> None:
    with TestClient(create_application()) as client:
        response = client.get("/api/v1/discovery")

    assert response.status_code == 200
    assert response.json() == {"status": "available"}


def test_discovery_credential_profile_routes_are_registered_in_openapi() -> None:
    app = create_application()
    paths = app.openapi()["paths"]

    assert "/api/v1/credentials/profiles" in paths
    assert "/api/v1/credentials/profiles/{profile_id}/test" in paths


def test_discovery_job_requires_authentication() -> None:
    with TestClient(create_application()) as client:
        response = client.get(
            "/api/v1/discovery/jobs",
            headers={"X-Tenant-ID": "tenant-a"},
        )

    assert response.status_code == 401


def test_snapshot_comparison_requires_authentication() -> None:
    with TestClient(create_application()) as client:
        response = client.post(
            "/api/v1/comparison",
            headers={"X-Tenant-ID": "tenant-a"},
            json={
                "expected_snapshot_id": "9c76945c-d8d0-4c46-b4bb-aeda00e43f78",
                "observed_snapshot_id": "6638eff2-f4bf-42a3-999a-ae88cfde7820",
            },
        )

    assert response.status_code == 401


def test_job_device_results_project_persisted_snapshot_model() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    tenant_id = "tenant-a"
    target_id = uuid4()
    run_id = uuid4()
    job_id = uuid4()
    snapshot_id = uuid4()
    try:
        session.add_all(
            [
                DiscoveryTargetRecord(
                    id=target_id,
                    tenant_id=tenant_id,
                    identifier="coreSW",
                    address="192.168.137.225",
                    credential_reference="profile-id",
                    metadata_json={},
                ),
                DiscoveryRunRecord(
                    id=run_id,
                    tenant_id=tenant_id,
                    target_identifier="coreSW",
                    target_address="192.168.137.225",
                    metadata_json={},
                ),
                DiscoveryJobRecord(
                    id=job_id,
                    tenant_id=tenant_id,
                    target_id=target_id,
                    run_id=run_id,
                    state="succeeded",
                    requested_capabilities={},
                ),
                DiscoveryDeviceResultRecord(
                    tenant_id=tenant_id,
                    discovery_job_id=job_id,
                    child_job_id=job_id,
                    address="192.168.137.225",
                    hostname="Radisson_Blu_BB",
                    vendor="Cisco",
                    platform="ios",
                    state="succeeded",
                    selected_transport="netmiko",
                ),
                SnapshotRecord(
                    id=snapshot_id,
                    source="live",
                    source_label="coreSW",
                    captured_at=datetime.now(UTC),
                    schema_version="1",
                    discovery_run_id=run_id,
                    payload={},
                    devices=[
                        SnapshotDeviceRecord(
                            device_id="coreSW",
                            name="Radisson_Blu_BB",
                            manufacturer="Cisco",
                            model="WS-C4506-E",
                            management_ip="192.168.137.225",
                            platform="ios",
                            payload={},
                        )
                    ],
                ),
            ]
        )
        session.commit()

        results = get_job_devices(job_id, session, None, tenant_id)

        assert len(results) == 1
        assert results[0].hostname == "Radisson_Blu_BB"
        assert results[0].model == "WS-C4506-E"
        assert results[0].platform == "ios"
    finally:
        session.close()
