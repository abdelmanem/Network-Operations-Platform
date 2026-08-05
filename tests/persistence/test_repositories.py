from __future__ import annotations

from collections.abc import Iterator

import pytest
from backend.app.comparison.engine import ComparisonEngine
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import (
    VLAN,
    Device,
    DeviceType,
    Interface,
    Manufacturer,
)
from backend.app.models.base import BaseModel
from backend.app.persistence.migrations import DiscoveryRunRecord
from backend.app.persistence.models import SnapshotSource
from backend.app.persistence.repositories import (
    FindingRepository,
    HistoryRepository,
    SnapshotRepository,
)
from backend.app.persistence.unit_of_work import PersistenceUnitOfWork
from backend.app.snapshot.entities import (
    DeviceSnapshot,
    InterfaceSnapshot,
    NeighborSnapshot,
    VLANSnapshot,
)
from backend.app.snapshot.entities import (
    InventorySnapshot as LiveInventorySnapshot,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    BaseModel.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    with session_factory() as db_session:
        yield db_session


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
                device_id="switch-01",
                name="switch-01",
                serial_number="XYZ999",
                management_ip="10.0.0.2",
                interfaces=(InterfaceSnapshot(device_id="switch-01", name="Gi1/0/1"),),
                vlans=(VLANSnapshot(vlan_id=10, name="staff"),),
                neighbors=(
                    NeighborSnapshot(
                        local_device_id="switch-01",
                        local_interface="Gi1/0/1",
                        remote_device_id="core-01",
                    ),
                ),
            ),
        ),
    )


def test_snapshot_repository_persists_immutable_live_snapshot(session: Session) -> None:
    history = HistoryRepository(session)
    snapshots = SnapshotRepository(session)
    discovery_run = history.create_discovery_run(
        "switch-01",
        target_address="10.0.0.2",
    )

    record = snapshots.add_live_snapshot(
        _live_snapshot(),
        discovery_run_id=discovery_run.id,
    )
    session.commit()

    loaded = snapshots.get(record.id)

    assert loaded is not None
    assert loaded.source == SnapshotSource.LIVE.value
    assert loaded.discovery_run_id == discovery_run.id
    assert loaded.devices[0].name == "switch-01"
    assert loaded.devices[0].interfaces[0].name == "Gi1/0/1"
    assert loaded.devices[0].vlans[0].vlan_id == 10
    assert loaded.devices[0].neighbors[0].remote_device_id == "core-01"


def test_finding_repository_persists_comparison_with_evidence(
    session: Session,
) -> None:
    snapshots = SnapshotRepository(session)
    finding_repository = FindingRepository(session)
    netbox_record = snapshots.add_netbox_snapshot(_netbox_snapshot())
    live_record = snapshots.add_live_snapshot(_live_snapshot())
    result = ComparisonEngine().compare(_netbox_snapshot(), _live_snapshot())

    comparison_record = finding_repository.add_comparison_result(
        result,
        expected_snapshot_id=netbox_record.id,
        observed_snapshot_id=live_record.id,
    )
    session.commit()

    loaded = finding_repository.get_comparison_result(comparison_record.id)

    assert loaded is not None
    assert loaded.expected_snapshot_id == netbox_record.id
    assert loaded.observed_snapshot_id == live_record.id
    assert loaded.metrics["total_findings"] == len(result.findings)
    assert loaded.findings
    assert loaded.findings[0].evidence


def test_persistence_unit_of_work_exposes_history_repositories(
    session: Session,
) -> None:
    with PersistenceUnitOfWork(session) as unit_of_work:
        run = unit_of_work.history.create_discovery_run("switch-02")
        unit_of_work.snapshots.add_live_snapshot(
            _live_snapshot(),
            discovery_run_id=run.id,
        )

    assert len(HistoryRepository(session).list_discovery_runs()) == 1
    assert len(SnapshotRepository(session).list()) == 1


def test_history_records_are_immutable_after_insert(session: Session) -> None:
    history = HistoryRepository(session)
    run = history.create_discovery_run("switch-03")
    session.commit()

    run.target_identifier = "changed"

    with pytest.raises(RuntimeError):
        session.flush()
    session.rollback()

    session.delete(run)
    with pytest.raises(RuntimeError):
        session.flush()


def test_persistence_models_are_registered_in_metadata() -> None:
    assert DiscoveryRunRecord.__tablename__ in BaseModel.metadata.tables
    assert "comparison_results" in BaseModel.metadata.tables
    assert "evidence" in BaseModel.metadata.tables
