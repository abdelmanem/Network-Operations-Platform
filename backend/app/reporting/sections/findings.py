"""Findings section builder."""

from __future__ import annotations

from types import MappingProxyType

from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import SectionType
from backend.app.reporting.models import ReportSection
from backend.app.reporting.statistics import ReportStatistics


def build_findings_section(
    context: ReportContext,
    statistics: ReportStatistics,
) -> ReportSection:
    """Build structured findings section data."""

    findings: tuple[dict[str, object], ...] = ()
    if context.comparison_result is not None:
        findings = tuple(
            {
                "finding_id": str(finding.id),
                "rule_id": str(finding.rule_id),
                "title": finding.title,
                "severity": finding.severity.level.value,
                "severity_score": finding.severity.score,
                "description": finding.description,
                "evidence_count": len(finding.evidence),
            }
            for finding in context.comparison_result.findings
        )

    return ReportSection(
        section_type=SectionType.FINDINGS,
        title="section.findings",
        data=MappingProxyType(
            {
                "findings": findings,
                "critical_findings": statistics.critical_findings,
                "major_findings": statistics.major_findings,
                "minor_findings": statistics.minor_findings,
            }
        ),
    )
