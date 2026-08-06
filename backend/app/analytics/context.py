"""Typed context objects for historical analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class HistoricalRunEntry:
    """Immutable discovery run metrics captured in persisted history."""

    run_id: UUID
    started_at: datetime
    completed_at: datetime
    total_devices: int
    successful_targets: int
    total_targets: int
    compliance_score: float | int
    critical_findings: int
    major_findings: int
    minor_findings: int
    missing_devices: int = 0
    extra_devices: int = 0
    changed_devices: int = 0
    discovered_devices: int = 0
    inventory_accuracy: float | None = None
    netbox_sync: float | None = None
    risk_score: float | None = None


@dataclass(frozen=True, slots=True)
class HistoricalFindingEntry:
    """Immutable persisted finding entry for historical trend analysis."""

    finding_id: UUID
    run_id: UUID
    title: str
    severity: str
    resolved: bool
    created_at: datetime
    resolved_at: datetime | None = None
    device_id: str | None = None
    platform: str | None = None
    vendor: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalAnalyticsContext:
    """Context consumed by the historical analytics engine."""

    runs: tuple[HistoricalRunEntry, ...] = field(default_factory=tuple)
    findings: tuple[HistoricalFindingEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "runs", tuple(self.runs))
        object.__setattr__(self, "findings", tuple(self.findings))
