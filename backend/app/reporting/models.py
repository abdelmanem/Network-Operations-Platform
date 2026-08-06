"""Immutable reporting domain models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from uuid import UUID

from backend.app.reporting.enums import (
    DocumentNodeType,
    ExportFormat,
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    ReportType,
    SectionType,
)
from backend.app.reporting.metadata import ReportMetadata
from backend.app.reporting.statistics import ReportStatistics


@dataclass(frozen=True, slots=True)
class ReportRecommendation:
    """Structured remediation recommendation without prose templates."""

    recommendation_id: str
    category: RecommendationCategory
    action: RecommendationAction
    priority: RecommendationPriority
    subject_type: str
    subject_id: str
    reason_code: str
    related_finding_ids: tuple[UUID, ...] = field(default_factory=tuple)
    related_difference_keys: tuple[str, ...] = field(default_factory=tuple)
    attributes: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True, slots=True)
class ReportSection:
    """Immutable report section payload."""

    section_type: SectionType
    title: str
    data: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class ReportData:
    """Immutable assembled report data."""

    report_type: ReportType
    metadata: ReportMetadata
    statistics: ReportStatistics
    sections: tuple[ReportSection, ...] = field(default_factory=tuple)
    recommendations: tuple[ReportRecommendation, ...] = field(default_factory=tuple)
    generated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DocumentNode:
    """Structured document tree node used by templates and exporters."""

    node_type: DocumentNodeType
    attributes: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
    children: tuple[DocumentNode, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RenderedDocument:
    """Intermediate rendered document consumed by exporters."""

    report_type: ReportType
    metadata: ReportMetadata
    root: DocumentNode
    statistics: ReportStatistics
    recommendations: tuple[ReportRecommendation, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Binary export output."""

    format: ExportFormat
    content: bytes
    mime_type: str
    filename: str
