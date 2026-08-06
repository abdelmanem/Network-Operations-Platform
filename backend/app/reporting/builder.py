"""Report data builder."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import ReportType, SectionType
from backend.app.reporting.metadata import ReportMetadata
from backend.app.reporting.models import ReportData, ReportSection
from backend.app.reporting.sections import (
    build_appendix_section,
    build_compliance_section,
    build_discrepancies_section,
    build_executive_summary_section,
    build_findings_section,
    build_inventory_section,
    build_metrics_section,
    build_recommendations,
    build_recommendations_section,
)
from backend.app.reporting.statistics import ReportStatistics, StatisticsCalculator
from backend.app.reporting.templates import TemplateRegistry

SectionBuilder = Callable[[ReportContext, ReportStatistics], ReportSection]


class ReportBuilder:
    """Assemble immutable report data without export formatting."""

    def __init__(
        self,
        *,
        statistics_calculator: StatisticsCalculator | None = None,
        template_registry: TemplateRegistry | None = None,
    ) -> None:
        self._statistics_calculator = statistics_calculator or StatisticsCalculator()
        self._template_registry = template_registry or TemplateRegistry()
        self._section_builders: dict[SectionType, SectionBuilder] = {
            SectionType.EXECUTIVE_SUMMARY: self._wrap(build_executive_summary_section),
            SectionType.INVENTORY: self._wrap(build_inventory_section),
            SectionType.COMPLIANCE: self._wrap(build_compliance_section),
            SectionType.FINDINGS: self._wrap(build_findings_section),
            SectionType.DISCREPANCIES: self._wrap(build_discrepancies_section),
            SectionType.METRICS: self._wrap(build_metrics_section),
            SectionType.APPENDIX: self._wrap(build_appendix_section),
        }

    def build(
        self,
        report_type: ReportType,
        context: ReportContext,
    ) -> ReportData:
        """Build report data for the requested report type."""

        statistics = self._statistics_calculator.calculate(context)
        recommendations = build_recommendations(context)
        template = self._template_registry.get(report_type)
        sections: list[ReportSection] = []

        for section_type in template.definition.sections:
            if section_type == SectionType.RECOMMENDATIONS:
                sections.append(
                    build_recommendations_section(context, statistics, recommendations)
                )
                continue
            builder = self._section_builders.get(section_type)
            if builder is None:
                continue
            sections.append(builder(context, statistics))

        metadata = ReportMetadata(
            title=template.definition.title_key,
            report_type=report_type,
            run_id=context.run_id,
            job_id=context.job_id,
            generated_at=datetime.now(UTC),
            site=context.site,
            device_role=context.device_role,
            platform=context.platform,
            source="cached_history",
        )
        return ReportData(
            report_type=report_type,
            metadata=metadata,
            statistics=statistics,
            sections=tuple(sections),
            recommendations=recommendations,
            generated_at=metadata.generated_at,
        )

    @staticmethod
    def _wrap(
        builder: Callable[..., ReportSection],
    ) -> SectionBuilder:
        def wrapped(
            context: ReportContext, statistics: ReportStatistics
        ) -> ReportSection:
            return builder(context, statistics)

        return wrapped
