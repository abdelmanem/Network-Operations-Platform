"""Structured recommendation builders for historical analytics."""

from __future__ import annotations

from backend.app.analytics.models import (
    AnalyticsRecommendation,
    AnalyticsRecommendationAction,
    AnalyticsRecommendationCategory,
    AnalyticsRecommendationPriority,
)


def build_recommendations_from_risk(
    risk_delta: float,
    recurring_findings: tuple[tuple[str, int], ...],
) -> tuple[AnalyticsRecommendation, ...]:
    """Return structured recommendation objects only."""

    recommendations: list[AnalyticsRecommendation] = []
    if risk_delta > 0:
        recommendations.append(
            AnalyticsRecommendation(
                category=AnalyticsRecommendationCategory.RISK,
                action=AnalyticsRecommendationAction.REMEDIATE,
                priority=AnalyticsRecommendationPriority.HIGH,
                message="Risk increased across historical runs.",
                subject="risk",
                reason="risk-delta",
            )
        )
    if recurring_findings:
        recommendations.append(
            AnalyticsRecommendation(
                category=AnalyticsRecommendationCategory.COMPLIANCE,
                action=AnalyticsRecommendationAction.INVESTIGATE,
                priority=AnalyticsRecommendationPriority.MEDIUM,
                message="Recurring findings suggest a persistent issue cluster.",
                subject="findings",
                reason="recurring-findings",
            )
        )
    if not recommendations:
        recommendations.append(
            AnalyticsRecommendation(
                category=AnalyticsRecommendationCategory.OPERATIONAL,
                action=AnalyticsRecommendationAction.MONITOR,
                priority=AnalyticsRecommendationPriority.LOW,
                message="Historical activity remains within expectations.",
                subject="history",
                reason="stable",
            )
        )
    return tuple(recommendations)
