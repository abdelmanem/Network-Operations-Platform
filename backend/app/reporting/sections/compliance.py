"""Compliance section builder."""

from __future__ import annotations

from types import MappingProxyType

from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import SectionType
from backend.app.reporting.models import ReportSection
from backend.app.reporting.statistics import ReportStatistics


def build_compliance_section(
    context: ReportContext,
    statistics: ReportStatistics,
) -> ReportSection:
    """Build structured compliance section data."""

    decision = context.evaluation_decision
    metrics = None
    status = None
    risk_score = None
    rule_results: tuple[dict[str, object], ...] = ()

    if decision is not None:
        status = decision.status.value
        risk_score = decision.risk_score
        if decision.metrics is not None:
            metrics = {
                "total_rules": decision.metrics.total_rules,
                "evaluated_rules": decision.metrics.evaluated_rules,
                "compliant": decision.metrics.compliant,
                "non_compliant": decision.metrics.non_compliant,
                "waived": decision.metrics.waived,
                "not_applicable": decision.metrics.not_applicable,
                "errors": decision.metrics.errors,
                "risk_score": decision.metrics.risk_score,
                "compliance_score": decision.metrics.compliance_score,
            }
        rule_results = tuple(
            {
                "rule_key": result.rule_key,
                "status": result.status.value,
                "passed": result.passed,
                "risk_score": result.risk_score,
                "severity": result.severity.level.value,
                "subject_type": result.difference.subject_type,
                "subject_id": result.difference.subject_id,
            }
            for result in decision.rule_results
        )

    return ReportSection(
        section_type=SectionType.COMPLIANCE,
        title="section.compliance",
        data=MappingProxyType(
            {
                "status": status,
                "risk_score": risk_score,
                "compliance_score": statistics.compliance_score,
                "metrics": metrics,
                "rule_results": rule_results,
            }
        ),
    )
