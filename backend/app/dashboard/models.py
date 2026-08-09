from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DashboardKpiSummary:
    total_devices: int | None = None
    reachable_devices: int | None = None
    unreachable_devices: int | None = None
    discovery_success_pct: float | None = None
    netbox_accuracy_pct: float | None = None
    missing_devices: int | None = None
    extra_devices: int | None = None
    modified_devices: int | None = None
    findings_total: int | None = None
    critical_findings: int | None = None
    major_findings: int | None = None
    minor_findings: int | None = None
    latest_run_id: UUID | None = None
    latest_run_started_at: datetime | None = None
    latest_run_finished_at: datetime | None = None
    unsupported_metrics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class DashboardAggregateBucket:
    period_label: str
    start: datetime
    end: datetime
    discovery_success_pct: float | None = None
    total_devices: int | None = None
    missing_devices: int | None = None
    extra_devices: int | None = None
    modified_devices: int | None = None
    findings_total: int | None = None


@dataclass(frozen=True, slots=True)
class DashboardTrendEntry:
    metric: str
    baseline_value: float | int | None = None
    current_value: float | int | None = None
    trend: Literal["stable", "increasing", "decreasing", "volatile"] = "stable"
    direction: Literal["up", "down", "flat"] = "flat"
    period_start: datetime | None = None
    period_end: datetime | None = None


@dataclass(frozen=True, slots=True)
class DashboardTrendsResponse:
    discovery_success_trend: DashboardTrendEntry
    device_count_trend: DashboardTrendEntry
    findings_count_trend: DashboardTrendEntry
    drift_trend: DashboardTrendEntry


@dataclass(frozen=True, slots=True)
class DashboardResponseEnvelope:
    summary: DashboardKpiSummary
    aggregates: tuple[DashboardAggregateBucket, ...]
    trends: DashboardTrendsResponse
