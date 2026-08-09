from __future__ import annotations

from collections.abc import Iterator

import pytest
from backend.app.api.v1.dependencies import get_db_session
from backend.app.comparison.engine import ComparisonEngine
from backend.app.core.application import create_application
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import (
    VLAN,
    Device,
    DeviceType,
    Interface,
    Manufacturer,
)
from backend.app.models.base import BaseModel
from backend.app.persistence.repositories import (
    FindingRepository,
    HistoryRepository,
    SnapshotRepository,
)
from backend.app.snapshot.entities import (
    DeviceSnapshot,
    InterfaceSnapshot,
    NeighborSnapshot,
    VLANSnapshot,
)
from backend.app.snapshot.entities import InventorySnapshot as LiveInventorySnapshot
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_application()

    def override_get_db_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client


def _netbox_snapshot() -> NetBoxInventorySnapshot:
    manufacturer = Manufacturer(name="Cisco", slug="cisco")
    device_type = DeviceType(
        manufacturer=manufacturer,
        model="WS-C2960X",
        slug="ws-c2960x",
    )
    return NetBoxInventorySnapshot(
        devices=(
            Device(
                name="switch-01",
                device_type=device_type,
                serial="ABC123",
                primary_ip="10.0.0.1",
                interfaces=(Interface(name="Gi1/0/1", device_name="switch-01"),),
            ),
        ),
        vlans=(VLAN(vid=10, name="users"),),
    )


def _live_snapshot() -> LiveInventorySnapshot:
    return LiveInventorySnapshot(
        source="collector",
        devices=(
            DeviceSnapshot(
                device_id="switch-02",
                name="switch-02",
                serial_number="XYZ999",
                management_ip="10.0.0.2",
                interfaces=(InterfaceSnapshot(device_id="switch-02", name="Gi1/0/1"),),
                vlans=(VLANSnapshot(vlan_id=10, name="staff"),),
                neighbors=(
                    NeighborSnapshot(
                        local_device_id="switch-02",
                        local_interface="Gi1/0/1",
                        remote_device_id="core-01",
                    ),
                ),
            ),
        ),
    )


def test_dashboard_kpis_returns_unsupported_metrics_when_no_data(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/dashboard/kpis")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_devices"] is None
    assert payload["netbox_accuracy_pct"] is None
    assert payload["unsupported_metrics"] == [
        "successful_targets",
        "failed_targets",
        "skipped_targets",
        "total_targets",
        "discovery_success_pct",
        "unreachable_devices",
    ]


def test_dashboard_aggregates_and_trends_return_expected_values(
    client: TestClient, db_session: Session
) -> None:
    history = HistoryRepository(db_session)
    snapshots = SnapshotRepository(db_session)
    finding_repository = FindingRepository(db_session)

    discovery_run = history.create_discovery_run("switch-01")
    live_record = snapshots.add_live_snapshot(
        _live_snapshot(),
        discovery_run_id=discovery_run.id,
    )
    netbox_record = snapshots.add_netbox_snapshot(_netbox_snapshot())
    comparison_result = ComparisonEngine().compare(_netbox_snapshot(), _live_snapshot())
    finding_repository.add_comparison_result(
        comparison_result,
        expected_snapshot_id=netbox_record.id,
        observed_snapshot_id=live_record.id,
    )
    db_session.commit()

    aggregates_response = client.get("/api/v1/dashboard/aggregates?granularity=daily")
    assert aggregates_response.status_code == 200
    aggregates_payload = aggregates_response.json()
    assert len(aggregates_payload["items"]) == 1
    assert aggregates_payload["items"][0]["missing_devices"] == 1

    trends_response = client.get("/api/v1/dashboard/trends")
    assert trends_response.status_code == 200
    trends_payload = trends_response.json()
    assert trends_payload["trends"]["device_count_trend"]["current_value"] == 1
    assert trends_payload["trends"]["findings_count_trend"]["current_value"] >= 0
    assert trends_payload["trends"]["drift_trend"]["current_value"] >= 0
