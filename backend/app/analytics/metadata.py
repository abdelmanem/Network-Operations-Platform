"""Reusable metadata models for historical analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AggregationGranularity(StrEnum):
    """Supported time-based aggregation buckets."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class BaselineDirection(StrEnum):
    """Baseline comparison direction."""

    CURRENT_VS_PREVIOUS = "current_vs_previous"
    CURRENT_VS_BASELINE = "current_vs_baseline"
    CURRENT_VS_FIRST_RUN = "current_vs_first_run"
    CURRENT_VS_SELECTED_RUN = "current_vs_selected_run"


@dataclass(frozen=True, slots=True)
class AggregationBucket:
    """Single bucket for aggregated run metrics."""

    granularity: AggregationGranularity
    start: datetime
    end: datetime
    period_label: str
    count: int
    compliance_score: float
    risk_score: float
    discovered_devices: int


@dataclass(frozen=True, slots=True)
class BaselineComparison:
    """Comparison result between a current run and a baseline run."""

    direction: BaselineDirection
    current_run_id: UUID
    baseline_run_id: UUID
    compliance_delta: float
    risk_delta: float


@dataclass(frozen=True, slots=True)
class ComparisonPoint:
    """Run-to-run comparison summary."""

    previous_run_id: UUID
    current_run_id: UUID
    compliance_delta: float
    risk_delta: float
    discovered_delta: int


@dataclass(frozen=True, slots=True)
class AnalyticsStatistics:
    """Historical statistics surfaced by the analytics engine."""

    device_growth: int
    vendor_distribution: dict[str, int]
    platform_distribution: dict[str, int]
    discovery_success_trend: float
    compliance_trend: float
    inventory_trend: float
    findings_trend: float
    risk_trend: float


@dataclass(frozen=True, slots=True)
class RiskAnalysis:
    """Historical risk analysis outputs."""

    risk_delta: float
    severity_movement: dict[str, int]
    risk_concentration: float
    top_recurring_findings: tuple[tuple[str, int], ...]
    unstable_devices: tuple[str, ...]
    unstable_platforms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """Timeline entry for analytics visualizations."""

    kind: str
    timestamp: datetime
    label: str
    value: float
