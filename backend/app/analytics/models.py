"""Domain models for historical analytics reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AnalyticsRecommendationCategory(StrEnum):
    """High-level recommendation category."""

    COMPLIANCE = "compliance"
    RISK = "risk"
    DISCOVERY = "discovery"
    INVENTORY = "inventory"
    OPERATIONAL = "operational"


class AnalyticsRecommendationPriority(StrEnum):
    """Recommendation priority."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalyticsRecommendationAction(StrEnum):
    """Suggested remediation action."""

    INVESTIGATE = "investigate"
    REMEDIATE = "remediate"
    MONITOR = "monitor"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class AnalyticsRecommendation:
    """Structured recommendation for historical trend analysis."""

    category: AnalyticsRecommendationCategory
    action: AnalyticsRecommendationAction
    priority: AnalyticsRecommendationPriority
    message: str
    subject: str
    reason: str


@dataclass(frozen=True, slots=True)
class AnalyticsTimelineEntry:
    """Timeline segment emitted by the analytics engine."""

    timestamp: datetime
    title: str
    details: str
    severity: str = "info"


@dataclass(frozen=True, slots=True)
class AnalyticsAnomaly:
    """Anomaly identified from historical signal changes."""

    title: str
    severity: str
    details: str
    score: float


@dataclass(frozen=True, slots=True)
class AnalyticsReport:
    """Immutable historical analytics report."""

    compliance_trend: str
    risk_trend: str
    discovery_trend: str
    finding_evolution: float
    recommendations: tuple[AnalyticsRecommendation, ...] = field(default_factory=tuple)
    anomalies: tuple[AnalyticsAnomaly, ...] = field(default_factory=tuple)
    timeline: tuple[AnalyticsTimelineEntry, ...] = field(default_factory=tuple)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
