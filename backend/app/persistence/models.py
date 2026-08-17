"""SQLAlchemy models for immutable discovery history."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import BaseModel


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SnapshotSource(StrEnum):
    """Persisted snapshot source types."""

    NETBOX = "netbox"
    LIVE = "live"


class DiscoveryRunStatus(StrEnum):
    """Discovery run lifecycle status."""

    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ImmutableHistoryMixin:
    """Common immutable history columns."""

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        unique=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )


class DiscoveryRunRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable discovery run record."""

    __tablename__ = "discovery_runs"

    target_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    target_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=DiscoveryRunStatus.STARTED.value,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    snapshots: Mapped[list[SnapshotRecord]] = relationship(
        back_populates="discovery_run",
        cascade="all, delete-orphan",
    )


class SnapshotRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable inventory snapshot record."""

    __tablename__ = "snapshots"

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    discovery_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("discovery_runs.id"),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    discovery_run: Mapped[DiscoveryRunRecord | None] = relationship(
        back_populates="snapshots"
    )
    devices: Mapped[list[SnapshotDeviceRecord]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )
    comparison_results_expected: Mapped[list[ComparisonResultRecord]] = relationship(
        back_populates="expected_snapshot",
        foreign_keys="ComparisonResultRecord.expected_snapshot_id",
    )
    comparison_results_observed: Mapped[list[ComparisonResultRecord]] = relationship(
        back_populates="observed_snapshot",
        foreign_keys="ComparisonResultRecord.observed_snapshot_id",
    )


class SnapshotDeviceRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable snapshot device record."""

    __tablename__ = "snapshot_devices"

    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("snapshots.id"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    management_ip: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    snapshot: Mapped[SnapshotRecord] = relationship(back_populates="devices")
    interfaces: Mapped[list[SnapshotInterfaceRecord]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
    vlans: Mapped[list[SnapshotVLANRecord]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
    neighbors: Mapped[list[SnapshotNeighborRecord]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )


class SnapshotInterfaceRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable snapshot interface record."""

    __tablename__ = "snapshot_interfaces"

    snapshot_device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("snapshot_devices.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    oper_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    speed_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    poe_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    device: Mapped[SnapshotDeviceRecord] = relationship(back_populates="interfaces")


class SnapshotVLANRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable snapshot VLAN record."""

    __tablename__ = "snapshot_vlans"

    snapshot_device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("snapshot_devices.id"),
        nullable=False,
        index=True,
    )
    vlan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    device: Mapped[SnapshotDeviceRecord] = relationship(back_populates="vlans")


class SnapshotNeighborRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable snapshot neighbor record."""

    __tablename__ = "snapshot_neighbors"

    snapshot_device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("snapshot_devices.id"),
        nullable=False,
        index=True,
    )
    local_interface: Mapped[str] = mapped_column(String(255), nullable=False)
    remote_device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    remote_interface: Mapped[str | None] = mapped_column(String(255), nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(64), nullable=True)

    device: Mapped[SnapshotDeviceRecord] = relationship(back_populates="neighbors")


class ComparisonResultRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable comparison result record."""

    __tablename__ = "comparison_results"

    expected_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("snapshots.id"),
        nullable=False,
        index=True,
    )
    observed_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("snapshots.id"),
        nullable=False,
        index=True,
    )
    compared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    expected_snapshot: Mapped[SnapshotRecord] = relationship(
        back_populates="comparison_results_expected",
        foreign_keys=[expected_snapshot_id],
    )
    observed_snapshot: Mapped[SnapshotRecord] = relationship(
        back_populates="comparison_results_observed",
        foreign_keys=[observed_snapshot_id],
    )
    findings: Mapped[list[FindingRecord]] = relationship(
        back_populates="comparison_result",
        cascade="all, delete-orphan",
    )


class FindingRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable finding record."""

    __tablename__ = "findings"

    comparison_result_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("comparison_results.id"),
        nullable=False,
        index=True,
    )
    finding_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    rule_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_state: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    observed_state: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    comparison_result: Mapped[ComparisonResultRecord] = relationship(
        back_populates="findings"
    )
    evidence: Mapped[list[EvidenceRecord]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
    )


class EvidenceRecord(ImmutableHistoryMixin, BaseModel):
    """Immutable evidence record."""

    __tablename__ = "evidence"

    finding_record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("findings.id"),
        nullable=False,
        index=True,
    )
    evidence_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    finding: Mapped[FindingRecord] = relationship(back_populates="evidence")


class NetBoxSyncJobRecord(ImmutableHistoryMixin, BaseModel):
    """Durable record of a NetBox synchronization job."""

    __tablename__ = "netbox_sync_jobs"

    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


_IMMUTABLE_MODELS = (
    DiscoveryRunRecord,
    SnapshotRecord,
    SnapshotDeviceRecord,
    SnapshotInterfaceRecord,
    SnapshotVLANRecord,
    SnapshotNeighborRecord,
    ComparisonResultRecord,
    FindingRecord,
    EvidenceRecord,
)


def _prevent_history_mutation(
    mapper: object,
    connection: object,
    target: object,
) -> None:
    raise RuntimeError("Immutable history records cannot be updated or deleted.")


for immutable_model in _IMMUTABLE_MODELS:
    event.listen(immutable_model, "before_update", _prevent_history_mutation)
    event.listen(immutable_model, "before_delete", _prevent_history_mutation)
