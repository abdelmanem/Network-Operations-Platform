"""Appendix section builder."""

from __future__ import annotations

from types import MappingProxyType

from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import SectionType
from backend.app.reporting.models import ReportSection
from backend.app.reporting.statistics import ReportStatistics


def build_appendix_section(
    context: ReportContext,
    statistics: ReportStatistics,
) -> ReportSection:
    """Build structured appendix section data."""

    evidence_items: tuple[dict[str, object], ...] = ()
    if context.comparison_result is not None:
        collected: list[dict[str, object]] = []
        for finding in context.comparison_result.findings:
            for item in finding.evidence:
                collected.append(
                    {
                        "evidence_id": str(item.id),
                        "source": item.source,
                        "description": item.description,
                        "reference": item.reference,
                        "finding_id": str(finding.id),
                    }
                )
        evidence_items = tuple(collected)

    if context.evaluation_decision is not None:
        for item in context.evaluation_decision.evidence:
            evidence_items = (
                *evidence_items,
                {
                    "evidence_id": str(item.id),
                    "source": item.source,
                    "description": item.description,
                    "reference": item.reference,
                    "finding_id": None,
                },
            )

    return ReportSection(
        section_type=SectionType.APPENDIX,
        title="section.appendix",
        data=MappingProxyType(
            {
                "evidence": evidence_items,
                "run_id": str(context.run_id) if context.run_id else None,
                "job_id": str(context.job_id) if context.job_id else None,
                "site": context.site,
                "device_role": context.device_role,
                "platform": context.platform,
                "total_devices": statistics.total_devices,
            }
        ),
    )
