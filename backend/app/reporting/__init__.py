"""Reporting and export engine."""

from backend.app.reporting.builder import ReportBuilder
from backend.app.reporting.context import (
    DiscoveryRunSnapshot,
    HistoricalRunSnapshot,
    ReportContext,
)
from backend.app.reporting.engine import ReportEngine
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
from backend.app.reporting.models import (
    DocumentNode,
    ExportResult,
    RenderedDocument,
    ReportData,
    ReportRecommendation,
    ReportSection,
)
from backend.app.reporting.renderer import ReportRenderer
from backend.app.reporting.service import ReportService
from backend.app.reporting.statistics import ReportStatistics, StatisticsCalculator
from backend.app.reporting.summary import ReportSummary, SummaryGenerator
from backend.app.reporting.templates import (
    DefaultReportTemplate,
    ReportTemplate,
    TemplateDefinition,
    TemplateRegistry,
)

__all__ = [
    "DefaultReportTemplate",
    "DiscoveryRunSnapshot",
    "DocumentNode",
    "DocumentNodeType",
    "ExportFormat",
    "ExportResult",
    "HistoricalRunSnapshot",
    "RecommendationAction",
    "RecommendationCategory",
    "RecommendationPriority",
    "RenderedDocument",
    "ReportBuilder",
    "ReportContext",
    "ReportData",
    "ReportEngine",
    "ReportMetadata",
    "ReportRecommendation",
    "ReportSection",
    "ReportService",
    "ReportStatistics",
    "ReportSummary",
    "ReportTemplate",
    "ReportType",
    "ReportRenderer",
    "SectionType",
    "StatisticsCalculator",
    "SummaryGenerator",
    "TemplateDefinition",
    "TemplateRegistry",
]
