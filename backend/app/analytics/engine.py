"""Historical analytics engine for immutable discovery history."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.analytics.anomalies import detect_anomalies
from backend.app.analytics.context import HistoricalAnalyticsContext
from backend.app.analytics.models import (
    AnalyticsRecommendation,
    AnalyticsRecommendationAction,
    AnalyticsRecommendationCategory,
    AnalyticsRecommendationPriority,
    AnalyticsReport,
    AnalyticsTimelineEntry,
)
from backend.app.analytics.trends import (
    calculate_finding_evolution,
    classify_trend,
)


@dataclass(slots=True)
class HistoricalAnalyticsEngine:
    """Build historical analytics reports from immutable persisted history."""

    def analyze(self, context: HistoricalAnalyticsContext) -> AnalyticsReport:
        """Analyze immutable historical runs and findings into a trend report."""

        if not context.runs:
            return AnalyticsReport(
                compliance_trend="stable",
                risk_trend="stable",
                discovery_trend="stable",
                finding_evolution=0.0,
                recommendations=(),
                anomalies=(),
                timeline=(),
                summary="No historical runs available.",
            )

        compliance_values = [float(run.compliance_score) for run in context.runs]
        risk_values = [float(run.risk_score or 0.0) for run in context.runs]
        discovery_values = [float(run.discovered_devices) for run in context.runs]

        total_findings = len(context.findings)
        resolved_findings = sum(1 for finding in context.findings if finding.resolved)
        recommendations = self._build_recommendations(context)
        anomalies = detect_anomalies(risk_values, compliance_values)
        timeline = self._build_timeline(context)

        return AnalyticsReport(
            compliance_trend=classify_trend(compliance_values),
            risk_trend=classify_trend(risk_values),
            discovery_trend=classify_trend(discovery_values),
            finding_evolution=calculate_finding_evolution(
                total_findings,
                resolved_findings,
            ),
            recommendations=recommendations,
            anomalies=anomalies,
            timeline=timeline,
            summary=self._build_summary(context),
            metadata={
                "run_count": len(context.runs),
                "finding_count": total_findings,
                "resolved_count": resolved_findings,
            },
        )

    def _build_recommendations(
        self,
        context: HistoricalAnalyticsContext,
    ) -> tuple[AnalyticsRecommendation, ...]:
        recommendations: list[AnalyticsRecommendation] = []
        latest_run = context.runs[-1]
        if latest_run.risk_score is not None and latest_run.risk_score > 0.4:
            recommendations.append(
                AnalyticsRecommendation(
                    category=AnalyticsRecommendationCategory.RISK,
                    action=AnalyticsRecommendationAction.REMEDIATE,
                    priority=AnalyticsRecommendationPriority.HIGH,
                    message=(
                        "Risk score climbed in the latest run; inspect the "
                        "affected devices."
                    ),
                    subject="latest-run",
                    reason="risk-increase",
                )
            )
        if any(finding.resolved is False for finding in context.findings):
            recommendations.append(
                AnalyticsRecommendation(
                    category=AnalyticsRecommendationCategory.COMPLIANCE,
                    action=AnalyticsRecommendationAction.INVESTIGATE,
                    priority=AnalyticsRecommendationPriority.MEDIUM,
                    message=(
                        "Open findings remain in history; focus remediation "
                        "efforts on recurring issues."
                    ),
                    subject="findings",
                    reason="open-findings",
                )
            )
        if recommendations:
            return tuple(recommendations)
        return (
            AnalyticsRecommendation(
                category=AnalyticsRecommendationCategory.OPERATIONAL,
                action=AnalyticsRecommendationAction.MONITOR,
                priority=AnalyticsRecommendationPriority.LOW,
                message=(
                    "Historical patterns remain stable; continue monitoring "
                    "for regressions."
                ),
                subject="history",
                reason="stable",
            ),
        )

    def _build_timeline(
        self,
        context: HistoricalAnalyticsContext,
    ) -> tuple[AnalyticsTimelineEntry, ...]:
        entries: list[AnalyticsTimelineEntry] = []
        for run in context.runs:
            entries.append(
                AnalyticsTimelineEntry(
                    timestamp=run.started_at,
                    title=f"Run {run.run_id.hex[:8]}",
                    details=(
                        f"Compliance {run.compliance_score}, risk "
                        f"{run.risk_score or 0.0}, devices {run.total_devices}"
                    ),
                    severity="info",
                )
            )
        for finding in context.findings:
            entries.append(
                AnalyticsTimelineEntry(
                    timestamp=finding.created_at,
                    title=f"Finding {finding.title}",
                    details=f"Severity {finding.severity}; resolved={finding.resolved}",
                    severity=(
                        "critical"
                        if finding.severity.lower() == "critical"
                        else "warning"
                    ),
                )
            )
        return tuple(sorted(entries, key=lambda e: e.timestamp, reverse=False))

    def _build_summary(self, context: HistoricalAnalyticsContext) -> str:
        latest_run = context.runs[-1]
        return (
            f"Historical analytics reviewed {len(context.runs)} runs and "
            f"{len(context.findings)} findings. The latest run reached "
            f"{latest_run.compliance_score}% compliance with risk "
            f"{latest_run.risk_score or 0.0}."
        )
