"""Reporting enumerations."""

from __future__ import annotations

from enum import StrEnum


class ReportType(StrEnum):
    """Supported report types."""

    EXECUTIVE_SUMMARY = "executive_summary"
    INVENTORY = "inventory"
    DISCOVERY = "discovery"
    COMPLIANCE = "compliance"
    DIFFERENCE = "difference"
    FINDING = "finding"
    HISTORICAL = "historical"
    TECHNICAL = "technical"


class ExportFormat(StrEnum):
    """Supported export formats."""

    HTML = "html"
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class SectionType(StrEnum):
    """Report section identifiers."""

    EXECUTIVE_SUMMARY = "executive_summary"
    INVENTORY = "inventory"
    COMPLIANCE = "compliance"
    FINDINGS = "findings"
    DISCREPANCIES = "discrepancies"
    RECOMMENDATIONS = "recommendations"
    METRICS = "metrics"
    APPENDIX = "appendix"


class RecommendationCategory(StrEnum):
    """Structured recommendation categories."""

    COMPLIANCE = "compliance"
    INVENTORY = "inventory"
    DISCOVERY = "discovery"
    OPERATIONS = "operations"


class RecommendationAction(StrEnum):
    """Structured recommendation actions."""

    REMEDIATE_DRIFT = "remediate_drift"
    UPDATE_SOURCE_OF_TRUTH = "update_source_of_truth"
    INVESTIGATE = "investigate"
    REVIEW_POLICY = "review_policy"
    SCHEDULE_MAINTENANCE = "schedule_maintenance"
    VERIFY_CONNECTIVITY = "verify_connectivity"


class RecommendationPriority(StrEnum):
    """Structured recommendation priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DocumentNodeType(StrEnum):
    """Structured document node types for rendering."""

    DOCUMENT = "document"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    KEY_VALUE = "key_value"
    METRIC = "metric"
    DIVIDER = "divider"
