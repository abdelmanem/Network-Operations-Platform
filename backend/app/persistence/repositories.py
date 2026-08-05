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
from backend.app.persistence.models import (
    ComparisonResultRecord,
    DiscoveryRunRecord,
    DiscoveryRunStatus,
    EvidenceRecord,
    FindingRecord,
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

        record = SnapshotRecord(
            id=uuid4(),
            source=SnapshotSource.NETBOX.value,
            source_label="netbox",
            captured_at=self._now_from_netbox_snapshot(),
            schema_version="netbox-canonical-v1",
            payload=self._json_safe(snapshot.model_dump(mode="json")),
        )
        self.session.add(record)
        return record

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


def _json_safe(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(value, default=str)))
