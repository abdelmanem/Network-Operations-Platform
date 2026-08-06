"""Pluggable structured report templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from backend.app.reporting.enums import ReportType, SectionType


@dataclass(frozen=True, slots=True)
class TemplateDefinition:
    """Declarative template definition without formatting logic."""

    report_type: ReportType
    title_key: str
    sections: tuple[SectionType, ...] = field(default_factory=tuple)
    layout: str = "default"


class ReportTemplate(Protocol):
    """Protocol for pluggable report templates."""

    @property
    def definition(self) -> TemplateDefinition:
        """Return the template definition."""

    def section_title(self, section_type: SectionType) -> str:
        """Return a structured section title key."""


@dataclass(frozen=True, slots=True)
class DefaultReportTemplate:
    """Default structured template for a report type."""

    definition: TemplateDefinition

    def section_title(self, section_type: SectionType) -> str:
        return f"section.{section_type.value}"


_SECTIONS_BY_REPORT: dict[ReportType, tuple[SectionType, ...]] = {
    ReportType.EXECUTIVE_SUMMARY: (
        SectionType.EXECUTIVE_SUMMARY,
        SectionType.METRICS,
        SectionType.RECOMMENDATIONS,
    ),
    ReportType.INVENTORY: (
        SectionType.INVENTORY,
        SectionType.METRICS,
        SectionType.APPENDIX,
    ),
    ReportType.DISCOVERY: (
        SectionType.EXECUTIVE_SUMMARY,
        SectionType.INVENTORY,
        SectionType.METRICS,
        SectionType.APPENDIX,
    ),
    ReportType.COMPLIANCE: (
        SectionType.EXECUTIVE_SUMMARY,
        SectionType.COMPLIANCE,
        SectionType.FINDINGS,
        SectionType.RECOMMENDATIONS,
        SectionType.METRICS,
    ),
    ReportType.DIFFERENCE: (
        SectionType.DISCREPANCIES,
        SectionType.METRICS,
        SectionType.APPENDIX,
    ),
    ReportType.FINDING: (
        SectionType.FINDINGS,
        SectionType.RECOMMENDATIONS,
        SectionType.APPENDIX,
    ),
    ReportType.HISTORICAL: (
        SectionType.EXECUTIVE_SUMMARY,
        SectionType.METRICS,
        SectionType.APPENDIX,
    ),
    ReportType.TECHNICAL: (
        SectionType.INVENTORY,
        SectionType.COMPLIANCE,
        SectionType.FINDINGS,
        SectionType.DISCREPANCIES,
        SectionType.METRICS,
        SectionType.APPENDIX,
    ),
}


class TemplateRegistry:
    """Registry of pluggable report templates."""

    def __init__(self) -> None:
        self._templates: dict[ReportType, ReportTemplate] = {}
        for report_type, sections in _SECTIONS_BY_REPORT.items():
            self.register(
                DefaultReportTemplate(
                    definition=TemplateDefinition(
                        report_type=report_type,
                        title_key=f"report.{report_type.value}",
                        sections=sections,
                    )
                )
            )

    def register(self, template: ReportTemplate) -> None:
        """Register or replace a report template."""

        self._templates[template.definition.report_type] = template

    def get(self, report_type: ReportType) -> ReportTemplate:
        """Return the template for a report type."""

        template = self._templates.get(report_type)
        if template is None:
            msg = f"No template registered for report type {report_type.value}"
            raise KeyError(msg)
        return template
