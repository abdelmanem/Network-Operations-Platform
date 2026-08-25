"""Persistence repositories for immutable discovery history."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from backend.app.comparison.result import InventoryComparisonResult
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import (
    Device as CanonicalDevice,
)
from backend.app.inventory.entities import (
    Interface as CanonicalInterface,
)
from backend.app.persistence.models import (
    ComparisonResultRecord,
    DiscoveryRunRecord,
    DiscoveryRunStatus,
    EvidenceRecord,
    FindingRecord,
    NetBoxSyncJobRecord,
    SnapshotDeviceRecord,
    SnapshotInterfaceRecord,
    SnapshotNeighborRecord,
    SnapshotRecord,
    SnapshotSource,
    SnapshotVLANRecord,
)
from backend.app.snapshot.entities import (
    DeviceSnapshot,
)
from backend.app.snapshot.entities import (
    InventorySnapshot as LiveInventorySnapshot,
)


@dataclass(slots=True)
class HistoryRepository:
    """Repository for discovery runs and historical timeline records."""

    session: Session

    def create_discovery_run(
        self,
        target_identifier: str,
        *,
        target_address: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> DiscoveryRunRecord:
        """Create an immutable discovery run record."""

        record = DiscoveryRunRecord(
            id=uuid4(),
            target_identifier=target_identifier,
            target_address=target_address,
            status=DiscoveryRunStatus.STARTED.value,
            metadata_json={} if metadata is None else dict(metadata),
        )
        self.session.add(record)
        return record

    def get_discovery_run(self, identity: UUID) -> DiscoveryRunRecord | None:
        """Return one discovery run by identifier."""

        return self.session.get(DiscoveryRunRecord, identity)

    def list_discovery_runs(self) -> tuple[DiscoveryRunRecord, ...]:
        """Return discovery runs ordered newest first."""

        statement = select(DiscoveryRunRecord).order_by(
            DiscoveryRunRecord.started_at.desc()
        )
        return tuple(self.session.scalars(statement).all())

    def timeline(self) -> tuple[DiscoveryRunRecord | ComparisonResultRecord, ...]:
        """Return immutable history timeline records."""

        discovery_runs = list(self.list_discovery_runs())
        comparisons = list(
            self.session.scalars(
                select(ComparisonResultRecord).order_by(
                    ComparisonResultRecord.compared_at.desc()
                )
            ).all()
        )
        return tuple(
            sorted(
                [*discovery_runs, *comparisons],
                key=lambda record: record.created_at,
                reverse=True,
            )
        )


@dataclass(slots=True)
class SnapshotRepository:
    """Repository for immutable NetBox and live snapshots."""

    session: Session

    def add_live_snapshot(
        self,
        snapshot: LiveInventorySnapshot,
        *,
        discovery_run_id: UUID | None = None,
    ) -> SnapshotRecord:
        """Persist one immutable live snapshot and child inventory records."""

        record = SnapshotRecord(
            id=uuid4(),
            source=SnapshotSource.LIVE.value,
            source_label=snapshot.source,
            captured_at=snapshot.captured_at,
            schema_version=snapshot.version,
            discovery_run_id=discovery_run_id,
            payload=self._json_safe(asdict(snapshot)),
        )
        record.devices = [self._device_record(device) for device in snapshot.devices]
        self.session.add(record)
        return record

    def add_netbox_snapshot(
        self,
        snapshot: NetBoxInventorySnapshot,
    ) -> SnapshotRecord:
        """Persist one immutable canonical NetBox inventory snapshot."""

        interfaces_by_device: dict[str, list[CanonicalInterface]] = {}
        for interface in getattr(snapshot, "interfaces", []):
            if getattr(interface, "device_name", None):
                interfaces_by_device.setdefault(interface.device_name, []).append(
                    interface
                )

        record = SnapshotRecord(
            id=uuid4(),
            source=SnapshotSource.NETBOX.value,
            source_label="netbox",
            captured_at=self._now_from_netbox_snapshot(),
            schema_version="netbox-canonical-v1",
            payload=self._json_safe(snapshot.model_dump(mode="json")),
        )
        record.devices = [
            self._netbox_device_record(
                device, interfaces_by_device.get(device.name, [])
            )
            for device in snapshot.devices
        ]
        self.session.add(record)
        return record

    def _netbox_device_record(
        self,
        device: CanonicalDevice,
        interfaces: list[CanonicalInterface],
    ) -> SnapshotDeviceRecord:
        record = SnapshotDeviceRecord(
            id=uuid4(),
            device_id=device.name,
            name=device.name,
            manufacturer=(
                device.device_type.manufacturer.name
                if device.device_type and device.device_type.manufacturer
                else None
            ),
            model=device.device_type.model if device.device_type else None,
            serial_number=device.serial,
            product_id=None,
            management_ip=device.primary_ip,
            platform=device.platform.name if device.platform else None,
            payload=self._json_safe(device.model_dump(mode="json")),
        )
        record.interfaces = [
            SnapshotInterfaceRecord(
                id=uuid4(),
                name=interface.name,
                admin_status="up" if getattr(interface, "enabled", True) else "down",
                oper_status=None,
                description=getattr(interface, "description", None),
                mac_address=getattr(interface, "mac_address", None),
                speed_mbps=None,
                poe_status=None,
            )
            for interface in interfaces
        ]
        return record

    def create_sync_job(self, job_id: UUID) -> NetBoxSyncJobRecord:
        """Create a new NetBox synchronization job record."""
        job = NetBoxSyncJobRecord(
            id=job_id,
            status="queued",
        )
        self.session.add(job)
        return job

    def get_sync_job(self, job_id: UUID) -> NetBoxSyncJobRecord | None:
        """Retrieve a specific NetBox synchronization job."""
        return self.session.get(NetBoxSyncJobRecord, job_id)

    def get_latest_sync_job(self) -> NetBoxSyncJobRecord | None:
        """Retrieve the most recent NetBox synchronization job."""
        statement = (
            select(NetBoxSyncJobRecord)
            .order_by(NetBoxSyncJobRecord.created_at.desc())
            .limit(1)
        )
        return self.session.scalars(statement).first()

    def get(self, identity: UUID) -> SnapshotRecord | None:
        """Return a snapshot with child records loaded."""

        statement = self._with_children(select(SnapshotRecord)).where(
            SnapshotRecord.id == identity
        )
        return self.session.scalars(statement).first()

    def list(self) -> tuple[SnapshotRecord, ...]:
        """Return all snapshots ordered by creation time."""

        statement = self._with_children(select(SnapshotRecord)).order_by(
            SnapshotRecord.created_at.desc()
        )
        return tuple(self.session.scalars(statement).all())

    def list_by_source(self, source: SnapshotSource) -> tuple[SnapshotRecord, ...]:
        """Return snapshots for one source type."""

        statement = self._with_children(select(SnapshotRecord)).where(
            SnapshotRecord.source == source.value
        )
        return tuple(self.session.scalars(statement).all())

    def get_latest(self, source: str) -> SnapshotRecord | None:
        """Return the most recent snapshot for a given source ('netbox' or 'live')."""

        source_value = source.lower() if source else ""
        statement = (
            self._with_children(select(SnapshotRecord))
            .where(SnapshotRecord.source == source_value)
            .order_by(SnapshotRecord.created_at.desc())
            .limit(1)
        )
        return self.session.scalars(statement).first()

    def get_latest_live_devices(self) -> tuple[SnapshotDeviceRecord, ...]:
        """Return all live devices across live snapshots, ordered by creation time descending."""
        statement = (
            select(SnapshotDeviceRecord)
            .join(SnapshotRecord)
            .where(SnapshotRecord.source == SnapshotSource.LIVE.value)
            .order_by(SnapshotDeviceRecord.created_at.desc())
            .options(
                selectinload(SnapshotDeviceRecord.interfaces),
                selectinload(SnapshotDeviceRecord.vlans),
                selectinload(SnapshotDeviceRecord.neighbors),
            )
        )
        return tuple(self.session.scalars(statement).all())

    def get_snapshot_devices(
        self,
        snapshot_id: UUID,
        device_id: str | None = None,
    ) -> tuple[SnapshotDeviceRecord, ...]:
        """Return all devices in a snapshot, optionally filtered by device_id."""

        statement = select(SnapshotDeviceRecord).where(
            SnapshotDeviceRecord.snapshot_id == snapshot_id
        )
        if device_id:
            statement = statement.where(SnapshotDeviceRecord.device_id == device_id)
        statement = statement.options(
            selectinload(SnapshotDeviceRecord.interfaces),
            selectinload(SnapshotDeviceRecord.vlans),
            selectinload(SnapshotDeviceRecord.neighbors),
        )
        return tuple(self.session.scalars(statement).all())

    def get_snapshot_interfaces(
        self,
        snapshot_id: UUID,
        device_id: str | None = None,
    ) -> tuple[SnapshotInterfaceRecord, ...]:
        """Return all interfaces in a snapshot, optionally filtered by device."""

        statement = (
            select(SnapshotInterfaceRecord)
            .join(SnapshotDeviceRecord)
            .where(SnapshotDeviceRecord.snapshot_id == snapshot_id)
        )
        if device_id:
            statement = statement.where(SnapshotDeviceRecord.device_id == device_id)
        return tuple(self.session.scalars(statement).all())

    def get_snapshot_vlans(
        self,
        snapshot_id: UUID,
        device_id: str | None = None,
    ) -> tuple[SnapshotVLANRecord, ...]:
        """Return all VLANs in a snapshot, optionally filtered by device."""

        statement = (
            select(SnapshotVLANRecord)
            .join(SnapshotDeviceRecord)
            .where(SnapshotDeviceRecord.snapshot_id == snapshot_id)
        )
        if device_id:
            statement = statement.where(SnapshotDeviceRecord.device_id == device_id)
        return tuple(self.session.scalars(statement).all())

    def get_snapshot_neighbors(
        self,
        snapshot_id: UUID,
        device_id: str | None = None,
    ) -> tuple[SnapshotNeighborRecord, ...]:
        """Return all neighbors in a snapshot, optionally filtered by device."""

        statement = (
            select(SnapshotNeighborRecord)
            .join(SnapshotDeviceRecord)
            .where(SnapshotDeviceRecord.snapshot_id == snapshot_id)
        )
        if device_id:
            statement = statement.where(SnapshotDeviceRecord.device_id == device_id)
        return tuple(self.session.scalars(statement).all())

    def _device_record(self, device: DeviceSnapshot) -> SnapshotDeviceRecord:
        record = SnapshotDeviceRecord(
            id=uuid4(),
            device_id=device.device_id,
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model,
            serial_number=device.serial_number,
            product_id=device.product_id,
            management_ip=device.management_ip,
            platform=device.platform,
            payload=self._json_safe(asdict(device)),
        )
        record.interfaces = [
            SnapshotInterfaceRecord(
                id=uuid4(),
                name=interface.name,
                admin_status=interface.admin_status,
                oper_status=interface.oper_status,
                description=interface.description,
                mac_address=interface.mac_address,
                speed_mbps=interface.speed_mbps,
                poe_status=interface.poe_status,
            )
            for interface in device.interfaces
        ]
        record.vlans = [
            SnapshotVLANRecord(
                id=uuid4(),
                vlan_id=vlan.vlan_id,
                name=vlan.name,
                status=vlan.status,
            )
            for vlan in device.vlans
        ]
        record.neighbors = [
            SnapshotNeighborRecord(
                id=uuid4(),
                local_interface=neighbor.local_interface,
                remote_device_id=neighbor.remote_device_id,
                remote_interface=neighbor.remote_interface,
                protocol=neighbor.protocol,
            )
            for neighbor in device.neighbors
        ]
        return record

    @staticmethod
    def _with_children(
        statement: Select[tuple[SnapshotRecord]],
    ) -> Select[tuple[SnapshotRecord]]:
        return statement.options(
            selectinload(SnapshotRecord.devices).selectinload(
                SnapshotDeviceRecord.interfaces
            ),
            selectinload(SnapshotRecord.devices).selectinload(
                SnapshotDeviceRecord.vlans
            ),
            selectinload(SnapshotRecord.devices).selectinload(
                SnapshotDeviceRecord.neighbors
            ),
        )

    @staticmethod
    def _now_from_netbox_snapshot() -> datetime:
        from datetime import UTC, datetime

        return datetime.now(UTC)

    @staticmethod
    def _json_safe(value: object) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(json.dumps(value, default=str)))


@dataclass(slots=True)
class FindingRepository:
    """Repository for comparison results, findings, and evidence."""

    session: Session

    def add_comparison_result(
        self,
        result: InventoryComparisonResult,
        *,
        expected_snapshot_id: UUID,
        observed_snapshot_id: UUID,
    ) -> ComparisonResultRecord:
        """Persist one comparison result with findings and evidence."""

        record = ComparisonResultRecord(
            id=uuid4(),
            expected_snapshot_id=expected_snapshot_id,
            observed_snapshot_id=observed_snapshot_id,
            compared_at=result.compared_at,
            metrics=(
                {} if result.metrics is None else _json_safe(asdict(result.metrics))
            ),
        )
        record.findings = [
            FindingRecord(
                id=uuid4(),
                finding_id=finding.id,
                rule_id=finding.rule_id,
                title=finding.title,
                severity=finding.severity.level.value,
                description=finding.description,
                expected_state=_json_safe(dict(finding.expected_state)),
                observed_state=_json_safe(dict(finding.observed_state)),
                evidence=[
                    EvidenceRecord(
                        id=uuid4(),
                        evidence_id=evidence.id,
                        source=evidence.source,
                        description=evidence.description,
                        reference=evidence.reference,
                        captured_at=evidence.captured_at,
                        details=_json_safe(dict(evidence.details)),
                    )
                    for evidence in finding.evidence
                ],
            )
            for finding in result.findings
        ]
        self.session.add(record)
        return record

    def get_comparison_result(self, identity: UUID) -> ComparisonResultRecord | None:
        """Return one comparison result with findings and evidence."""

        statement = (
            select(ComparisonResultRecord)
            .options(
                selectinload(ComparisonResultRecord.findings).selectinload(
                    FindingRecord.evidence
                )
            )
            .where(ComparisonResultRecord.id == identity)
        )
        return self.session.scalars(statement).first()

    def list_findings(self) -> tuple[FindingRecord, ...]:
        """Return all persisted finding records."""

        statement = select(FindingRecord).options(selectinload(FindingRecord.evidence))
        return tuple(self.session.scalars(statement).all())

    def list_by_device(self, device_id: str) -> tuple[FindingRecord, ...]:
        """Return all findings for a specific device."""

        statement = (
            select(FindingRecord)
            .options(selectinload(FindingRecord.evidence))
            .where(FindingRecord.expected_state.op("->>")("device_id") == device_id)
        )
        return tuple(self.session.scalars(statement).all())

    def get_latest_comparison(self) -> ComparisonResultRecord | None:
        """Return the most recent comparison result."""

        statement = (
            select(ComparisonResultRecord)
            .options(
                selectinload(ComparisonResultRecord.findings).selectinload(
                    FindingRecord.evidence
                )
            )
            .order_by(ComparisonResultRecord.compared_at.desc())
            .limit(1)
        )
        return self.session.scalars(statement).first()


def _json_safe(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(value, default=str)))
