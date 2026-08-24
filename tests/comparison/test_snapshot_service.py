from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from backend.app.api.v1.comparison import compare_existing_snapshots
from backend.app.api.v1.devices import _match_device_by_identity, compare_device
from backend.app.comparison.snapshot_service import (
    SnapshotComparisonError,
    SnapshotComparisonService,
)
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import Device, DeviceType, Manufacturer, Platform
from backend.app.models.base import BaseModel
from backend.app.persistence.models import DiscoveryRunRecord
from backend.app.persistence.repositories import FindingRepository, SnapshotRepository
from backend.app.schemas.comparison import SnapshotComparisonRequest
from backend.app.snapshot.entities import DeviceSnapshot, InventorySnapshot
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

LIVE_SNAPSHOT_ID = UUID("6638eff2-f4bf-42a3-999a-ae88cfde7820")
NETBOX_SNAPSHOT_ID = UUID("9c76945c-d8d0-4c46-b4bb-aeda00e43f78")


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    return Session(engine)


def _seed_snapshots(session: Session) -> None:
    run_id = UUID("e1852329-6c8b-44b1-9b7d-80865a621b34")
    expected = NetBoxInventorySnapshot(
        devices=(
            Device(
                name="Radisson_Blu_BB",
                serial="FOX1208GJ74",
                primary_ip="192.168.40.1/24",
                device_type=DeviceType(
                    manufacturer=Manufacturer(name="Cisco", slug="cisco"),
                    model="WS-C4506-E",
                    slug="ws-c4506-e",
                ),
                platform=Platform(
                    name="Cisco_SW_Routers",
                    slug="cisco-sw-routers",
                ),
            ),
        )
    )
    observed = InventorySnapshot(
        devices=(
            DeviceSnapshot(
                device_id="coreSW",
                name="Radisson_Blu_BB",
                manufacturer="Cisco",
                model="WS-C4506-E",
                serial_number="FOX1208GJ74",
                management_ip="192.168.137.225",
                platform="ios",
            ),
        ),
        source="coreSW",
    )

    session.add(
        DiscoveryRunRecord(
            id=run_id,
            tenant_id="tenant-a",
            target_identifier="coreSW",
            target_address="192.168.137.225",
            metadata_json={},
        )
    )
    repository = SnapshotRepository(session)
    expected_id = repository.add_netbox_snapshot(expected).id
    live_id = repository.add_live_snapshot(
        observed,
        discovery_run_id=run_id,
    ).id

    global NETBOX_SNAPSHOT_ID, LIVE_SNAPSHOT_ID
    NETBOX_SNAPSHOT_ID = expected_id
    LIVE_SNAPSHOT_ID = live_id

    session.commit()


def test_compares_existing_snapshots_and_persists_findings_and_evidence() -> None:
    session = _session()
    try:
        _seed_snapshots(session)

        result_id = SnapshotComparisonService(session).compare(
            expected_snapshot_id=NETBOX_SNAPSHOT_ID,
            observed_snapshot_id=LIVE_SNAPSHOT_ID,
            tenant_id="tenant-a",
        )

        result = FindingRepository(session).get_comparison_result(result_id)
        assert result is not None
        assert result.expected_snapshot_id == NETBOX_SNAPSHOT_ID
        assert result.observed_snapshot_id == LIVE_SNAPSHOT_ID
        assert result.metrics["modified"] >= 1
        assert result.findings
        assert all(finding.evidence for finding in result.findings)
        primary_ip_finding = next(
            finding
            for finding in result.findings
            if finding.expected_state.get("value") == "192.168.40.1/24"
        )
        assert primary_ip_finding.observed_state["value"] == "192.168.137.225"
    finally:
        session.close()


def test_rejects_live_snapshot_from_another_tenant() -> None:
    session = _session()
    try:
        _seed_snapshots(session)

        with pytest.raises(SnapshotComparisonError, match="not available"):
            SnapshotComparisonService(session).compare(
                expected_snapshot_id=NETBOX_SNAPSHOT_ID,
                observed_snapshot_id=LIVE_SNAPSHOT_ID,
                tenant_id="tenant-b",
            )
    finally:
        session.close()


def test_comparison_endpoint_returns_persisted_result_id_and_status() -> None:
    session = _session()
    try:
        _seed_snapshots(session)

        response = compare_existing_snapshots(
            SnapshotComparisonRequest(
                expected_snapshot_id=NETBOX_SNAPSHOT_ID,
                observed_snapshot_id=LIVE_SNAPSHOT_ID,
            ),
            session,
            None,
            "tenant-a",
        )

        assert response.status == "completed"
        assert response.id == FindingRepository(session).get_latest_comparison().id
    finally:
        session.close()


def test_device_compare_matches_logical_device_when_device_id_differs() -> None:
    session = _session()
    try:
        _seed_snapshots(session)

        result_id = SnapshotComparisonService(session).compare(
            expected_snapshot_id=NETBOX_SNAPSHOT_ID,
            observed_snapshot_id=LIVE_SNAPSHOT_ID,
            tenant_id="tenant-a",
        )

        response = compare_device(
            db_session=session,
            device_id="Radisson_Blu_BB",
            run_id=result_id,
        )

        assert response.expected_state is not None
        assert response.observed_state is not None
        assert response.expected_state.name == "Radisson_Blu_BB"
        assert response.observed_state.name == "Radisson_Blu_BB"
        assert response.expected_state.model == "WS-C4506-E"
        assert response.observed_state.model == "WS-C4506-E"
        assert response.expected_state.serial_number == "FOX1208GJ74"
        assert response.observed_state.serial_number == "FOX1208GJ74"
        assert response.observed_state.device_id == "coreSW"
        assert response.variances
    finally:
        session.close()


def test_device_identity_match_falls_back_to_serial() -> None:
    device = SimpleNamespace(
        device_id="coreSW",
        name="unavailable-name",
        serial_number="FOX1208GJ74",
    )

    matched = _match_device_by_identity(
        (device,),
        name="Radisson_Blu_BB",
        serial_number="FOX1208GJ74",
    )

    assert matched is device
