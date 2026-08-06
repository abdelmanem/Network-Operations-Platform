from __future__ import annotations

from backend.app.analytics.engine import HistoricalAnalyticsEngine
from tests.fixtures.analytics.golden_history import build_context


def test_engine_builds_report_with_trends_and_recommendations() -> None:
    context = build_context()
    engine = HistoricalAnalyticsEngine()

    report = engine.analyze(context)

    assert report.compliance_trend in {"increasing", "stable", "decreasing", "volatile"}
    assert report.risk_trend in {"increasing", "stable", "decreasing", "volatile"}
    assert report.discovery_trend in {"increasing", "stable", "decreasing", "volatile"}
    assert report.finding_evolution >= 0
    assert len(report.recommendations) >= 1
    assert report.anomalies
    assert report.timeline
