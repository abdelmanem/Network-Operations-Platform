from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardGranularity(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class DashboardTrendMetric(StrEnum):
    discovery_success = "discovery_success"
    device_count = "device_count"
    findings_count = "findings_count"
    drift = "drift"


class DashboardKpiSummaryResponse(BaseModel):
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
    unsupported_metrics: tuple[str, ...] = Field(default_factory=tuple)


class DashboardAggregateBucketResponse(BaseModel):
    period_label: str
    start: datetime
    end: datetime
    discovery_success_pct: float | None = None
    total_devices: int | None = None
    missing_devices: int | None = None
    extra_devices: int | None = None
    modified_devices: int | None = None
    findings_total: int | None = None


class DashboardTrendEntryResponse(BaseModel):
    metric: DashboardTrendMetric
    baseline_value: float | int | None = None
    current_value: float | int | None = None
    trend: Literal["stable", "increasing", "decreasing", "volatile"]
    direction: Literal["up", "down", "flat"]
    period_start: datetime | None = None
    period_end: datetime | None = None


class DashboardTrendsResponse(BaseModel):
    discovery_success_trend: DashboardTrendEntryResponse
    device_count_trend: DashboardTrendEntryResponse
    findings_count_trend: DashboardTrendEntryResponse
    drift_trend: DashboardTrendEntryResponse


class DashboardKpiRequest(BaseModel):
    site: str | None = None
    device_role: str | None = None
    platform: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class DashboardAggregatesRequest(DashboardKpiRequest):
    granularity: DashboardGranularity = DashboardGranularity.daily


class DashboardTrendsRequest(DashboardKpiRequest):
    pass


class DashboardAggregatesResponse(BaseModel):
    items: list[DashboardAggregateBucketResponse] = Field(default_factory=list)


class DashboardTrendsResponseEnvelope(BaseModel):
    trends: DashboardTrendsResponse
