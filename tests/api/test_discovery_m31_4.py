from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
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
    assert "/api/v1/discovery/jobs/{job_id}/cancel" in paths
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


def test_discovery_job_cancellation_requires_authentication() -> None:
    with TestClient(create_application()) as client:
        response = client.post(
            "/api/v1/discovery/jobs/9c76945c-d8d0-4c46-b4bb-aeda00e43f78/cancel",
            headers={"X-Tenant-ID": "tenant-a"},
            json={"reason": "operator requested stop"},
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

def test_get_cidr_variance_api() -> None:
    from backend.app.api.v1.discovery import get_cidr_variance

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)

    tenant_id = "tenant-a"
    target_id = uuid4()
    run_id = uuid4()
    job_id = uuid4()
    netbox_snap_id = uuid4()
    live_snap_id = uuid4()

    try:
        session.add_all([
            DiscoveryTargetRecord(
                id=target_id,
                tenant_id=tenant_id,
                identifier="test-cidr",
                address="192.168.40.0/24",
                scope_type="cidr_network",
                scope_cidr="192.168.40.0/24",
                metadata_json={},
                credential_reference="",
            ),
            DiscoveryRunRecord(
                id=run_id,
                tenant_id=tenant_id,
                target_identifier="test-cidr",
                target_address="192.168.40.0/24",
                started_at=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
                status="succeeded",
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
            SnapshotRecord(
                id=netbox_snap_id,
                source="netbox",
                tenant_id=tenant_id,
                captured_at=datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
                schema_version="1",
                payload={},
                devices=[
                    SnapshotDeviceRecord(device_id="dev1", name="sw-01", management_ip="192.168.40.10", serial_number="SN001", payload={}),
                    SnapshotDeviceRecord(device_id="dev2", name="sw-02", management_ip="192.168.40.20", serial_number="SN002", payload={})
                ]
            ),
            DiscoveryDeviceResultRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                discovery_job_id=job_id,
                child_job_id=uuid4(),
                address="192.168.40.10",
                hostname="sw-01",
                state="succeeded",
                result_state="discovered",
            ),
            DiscoveryDeviceResultRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                discovery_job_id=job_id,
                child_job_id=uuid4(),
                address="192.168.40.30",
                hostname="sw-03",
                state="succeeded",
                result_state="discovered",
            ),
            DiscoveryDeviceResultRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                discovery_job_id=job_id,
                child_job_id=uuid4(),
                address="192.168.40.40",
                state="succeeded",
                result_state="reachable_no_management",
                failure_code="TRANSPORT_UNAVAILABLE"
            ),
            SnapshotRecord(
                id=live_snap_id,
                source="live",
                tenant_id=tenant_id,
                discovery_run_id=run_id,
                captured_at=datetime(2024, 1, 1, 12, 10, tzinfo=UTC),
                schema_version="1",
                payload={},
                devices=[
                    SnapshotDeviceRecord(device_id="ldev1", name="sw-01", management_ip="192.168.40.10", serial_number="SN001", payload={})
                ]
            )
        ])
        session.commit()

        result = get_cidr_variance(job_id, session, None, tenant_id)

        assert result.summary.discovered == 2
        assert result.summary.netbox == 2
        assert result.summary.matched == 1
        assert result.summary.variances == 2
        assert result.summary.netbox_only == 1
        assert result.summary.discovered_only == 1
        assert result.summary.unverified == 1

        assert result.variances.netbox_only[0].address == "192.168.40.20"
        assert result.variances.discovered_only[0].address == "192.168.40.30"
        assert result.variances.unverified[0].address == "192.168.40.40"
    finally:
        session.close()


def test_cidr_variance_uses_tenant_and_deterministic_netbox_snapshot() -> None:
    from backend.app.api.v1.discovery import get_cidr_variance

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    tenant_id = "tenant-a"
    target_id = uuid4()
    run_id = uuid4()
    job_id = uuid4()
    captured_at = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    try:
        session.add_all(
            [
                DiscoveryTargetRecord(
                    id=target_id,
                    tenant_id=tenant_id,
                    identifier="test-cidr",
                    address="192.168.50.0/24",
                    scope_type="cidr_network",
                    scope_cidr="192.168.50.0/24",
                    metadata_json={},
                    credential_reference="",
                ),
                DiscoveryRunRecord(
                    id=run_id,
                    tenant_id=tenant_id,
                    target_identifier="test-cidr",
                    target_address="192.168.50.0/24",
                    started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
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
                SnapshotRecord(
                    id=UUID("00000000-0000-0000-0000-000000000001"),
                    tenant_id=tenant_id,
                    source="netbox",
                    captured_at=captured_at,
                    schema_version="1",
                    payload={},
                    devices=[
                        SnapshotDeviceRecord(
                            device_id="old",
                            name="old",
                            management_ip="192.168.50.10",
                            payload={},
                        )
                    ],
                ),
                SnapshotRecord(
                    id=UUID("00000000-0000-0000-0000-000000000002"),
                    tenant_id=tenant_id,
                    source="netbox",
                    captured_at=captured_at,
                    schema_version="1",
                    payload={},
                    devices=[
                        SnapshotDeviceRecord(
                            device_id="new",
                            name="new",
                            management_ip="192.168.50.20",
                            payload={},
                        )
                    ],
                ),
                SnapshotRecord(
                    id=uuid4(),
                    tenant_id="tenant-b",
                    source="netbox",
                    captured_at=datetime(2026, 1, 1, 11, 30, tzinfo=UTC),
                    schema_version="1",
                    payload={},
                    devices=[
                        SnapshotDeviceRecord(
                            device_id="other",
                            name="other",
                            management_ip="192.168.50.30",
                            payload={},
                        )
                    ],
                ),
            ]
        )
        session.commit()

        result = get_cidr_variance(job_id, session, None, tenant_id)

        assert result.summary.netbox == 1
        assert result.variances.netbox_only[0].address == "192.168.50.20"
    finally:
        session.close()


def test_cidr_variance_rejects_non_cidr_and_handles_missing_netbox_snapshot() -> None:
    from backend.app.api.v1.discovery import get_cidr_variance

    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    session = Session(engine)
    tenant_id = "tenant-a"
    target_id = uuid4()
    run_id = uuid4()
    job_id = uuid4()
    try:
        session.add_all(
            [
                DiscoveryTargetRecord(
                    id=target_id,
                    tenant_id=tenant_id,
                    identifier="single",
                    address="192.168.60.10",
                    scope_type="single_device",
                    metadata_json={},
                    credential_reference="",
                ),
                DiscoveryRunRecord(
                    id=run_id,
                    tenant_id=tenant_id,
                    target_identifier="single",
                    target_address="192.168.60.10",
                    started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
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
            ]
        )
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            get_cidr_variance(job_id, session, None, tenant_id)
        assert exc_info.value.status_code == 422

        target = session.get(DiscoveryTargetRecord, target_id)
        assert target is not None
        target.scope_type = "cidr_network"
        target.scope_cidr = "192.168.60.0/24"
        session.commit()
        result = get_cidr_variance(job_id, session, None, tenant_id)
        assert result.summary.netbox == 0
        assert result.summary.variances == 0
    finally:
        session.close()
