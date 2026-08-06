"""Report section builders."""

from __future__ import annotations

from backend.app.reporting.sections.appendix import build_appendix_section
from backend.app.reporting.sections.compliance import build_compliance_section
from backend.app.reporting.sections.discrepancies import build_discrepancies_section
from backend.app.reporting.sections.executive_summary import (
    build_executive_summary_section,
)
from backend.app.reporting.sections.findings import build_findings_section
from backend.app.reporting.sections.inventory import build_inventory_section
from backend.app.reporting.sections.metrics import build_metrics_section
from backend.app.reporting.sections.recommendations import (
    build_recommendations,
    build_recommendations_section,
)

__all__ = [
    "build_appendix_section",
    "build_compliance_section",
    "build_discrepancies_section",
    "build_executive_summary_section",
    "build_findings_section",
    "build_inventory_section",
    "build_metrics_section",
    "build_recommendations",
    "build_recommendations_section",
]
