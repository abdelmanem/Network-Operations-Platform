"""Domain-wide compliance enums."""

from __future__ import annotations

from enum import StrEnum


class RuleStatus(StrEnum):
    """Lifecycle status for a compliance rule."""

    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"


class ComparisonStatus(StrEnum):
    """Result status for a compliance comparison."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
