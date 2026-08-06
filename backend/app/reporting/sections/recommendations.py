"""Recommendations section builder."""

from __future__ import annotations

from types import MappingProxyType
from uuid import uuid4

from backend.app.comparison.diff import DifferenceType
from backend.app.compliance.findings.severity import SeverityLevel
from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import (
    RecommendationAction,
    RecommendationCategory,
    RecommendationPriority,
    SectionType,
)
from backend.app.reporting.models import ReportRecommendation, ReportSection
from backend.app.reporting.statistics import ReportStatistics


def build_recommendations(
    context: ReportContext,
) -> tuple[ReportRecommendation, ...]:
    """Generate structured recommendations from cached findings and differences."""

    recommendations: list[ReportRecommendation] = []
    comparison = context.comparison_result
    if comparison is None:
        return tuple(recommendations)

    for finding in comparison.findings:
        priority = _priority_from_severity(finding.severity.level)
        recommendations.append(
            ReportRecommendation(
                recommendation_id=str(uuid4()),
                category=RecommendationCategory.COMPLIANCE,
                action=RecommendationAction.REMEDIATE_DRIFT,
                priority=priority,
                subject_type="finding",
                subject_id=str(finding.id),
                reason_code=f"finding.{finding.severity.level.value}",
                related_finding_ids=(finding.id,),
            )
        )

    for difference in comparison.differences:
        action = _action_for_difference(difference.difference_type)
        category = RecommendationCategory.INVENTORY
        recommendations.append(
            ReportRecommendation(
                recommendation_id=str(uuid4()),
                category=category,
                action=action,
                priority=_priority_for_difference(difference.difference_type),
                subject_type=difference.subject_type,
                subject_id=difference.subject_id,
                reason_code=f"difference.{difference.difference_type.value}",
                related_difference_keys=(difference.key,),
            )
        )

    if context.discovery_run is not None and context.discovery_run.failed_targets > 0:
        recommendations.append(
            ReportRecommendation(
                recommendation_id=str(uuid4()),
                category=RecommendationCategory.DISCOVERY,
                action=RecommendationAction.VERIFY_CONNECTIVITY,
                priority=RecommendationPriority.HIGH,
                subject_type="discovery_run",
                subject_id=str(context.discovery_run.run_id),
                reason_code="discovery.failed_targets",
                attributes={"failed_targets": context.discovery_run.failed_targets},
            )
        )

    return tuple(recommendations)


def build_recommendations_section(
    context: ReportContext,
    statistics: ReportStatistics,
    recommendations: tuple[ReportRecommendation, ...],
) -> ReportSection:
    """Build structured recommendations section data."""

    payload = tuple(
        {
            "recommendation_id": item.recommendation_id,
            "category": item.category.value,
            "action": item.action.value,
            "priority": item.priority.value,
            "subject_type": item.subject_type,
            "subject_id": item.subject_id,
            "reason_code": item.reason_code,
            "related_finding_ids": [str(value) for value in item.related_finding_ids],
            "related_difference_keys": list(item.related_difference_keys),
            "attributes": dict(item.attributes),
        }
        for item in recommendations
    )
    return ReportSection(
        section_type=SectionType.RECOMMENDATIONS,
        title="section.recommendations",
        data=MappingProxyType(
            {
                "recommendations": payload,
                "count": len(recommendations),
                "critical_findings": statistics.critical_findings,
            }
        ),
    )


def _priority_from_severity(level: SeverityLevel) -> RecommendationPriority:
    if level == SeverityLevel.CRITICAL:
        return RecommendationPriority.CRITICAL
    if level == SeverityLevel.HIGH:
        return RecommendationPriority.HIGH
    if level == SeverityLevel.MEDIUM:
        return RecommendationPriority.MEDIUM
    return RecommendationPriority.LOW


def _action_for_difference(difference_type: DifferenceType) -> RecommendationAction:
    if difference_type == DifferenceType.MISSING:
        return RecommendationAction.INVESTIGATE
    if difference_type == DifferenceType.UNEXPECTED:
        return RecommendationAction.UPDATE_SOURCE_OF_TRUTH
    return RecommendationAction.REMEDIATE_DRIFT


def _priority_for_difference(difference_type: DifferenceType) -> RecommendationPriority:
    if difference_type in {DifferenceType.MISSING, DifferenceType.CONFLICT}:
        return RecommendationPriority.HIGH
    if difference_type == DifferenceType.UNEXPECTED:
        return RecommendationPriority.MEDIUM
    return RecommendationPriority.LOW
