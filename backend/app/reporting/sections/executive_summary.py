"""Executive summary section builder."""

from __future__ import annotations

from types import MappingProxyType

from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import SectionType
from backend.app.reporting.models import ReportSection
from backend.app.reporting.statistics import ReportStatistics
from backend.app.reporting.summary import SummaryGenerator


def build_executive_summary_section(
    context: ReportContext,
    statistics: ReportStatistics,
) -> ReportSection:
    """Build structured executive summary section data."""

    summary = SummaryGenerator().generate(context, statistics)
    return ReportSection(
        section_type=SectionType.EXECUTIVE_SUMMARY,
        title="section.executive_summary",
        data=MappingProxyType(
            {
                "headline": summary.headline,
                "highlights": summary.highlights,
                "metrics": dict(summary.metrics),
                "run_id": str(context.run_id) if context.run_id else None,
            }
        ),
    )
