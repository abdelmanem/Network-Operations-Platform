"""Service wrapper for historical analytics."""

from __future__ import annotations

from backend.app.analytics.context import HistoricalAnalyticsContext
from backend.app.analytics.engine import HistoricalAnalyticsEngine
from backend.app.analytics.models import AnalyticsReport


class HistoricalAnalyticsService:
    """Convenience service for generating analytics reports from context."""

    def __init__(self, engine: HistoricalAnalyticsEngine | None = None) -> None:
        self.engine = engine or HistoricalAnalyticsEngine()

    def analyze(self, context: HistoricalAnalyticsContext) -> AnalyticsReport:
        """Return a historical analytics report for the supplied context."""

        return self.engine.analyze(context)
