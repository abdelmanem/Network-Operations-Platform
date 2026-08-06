"""Reusable repository layer for analytics over immutable history."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.analytics.context import (
    HistoricalAnalyticsContext,
    HistoricalFindingEntry,
    HistoricalRunEntry,
)


@dataclass(slots=True)
class HistoricalAnalyticsRepository:
    """Read-only repository for analytics data sourced from immutable history."""

    runs: tuple[HistoricalRunEntry, ...] = field(default_factory=tuple)
    findings: tuple[HistoricalFindingEntry, ...] = field(default_factory=tuple)

    def build_context(self) -> HistoricalAnalyticsContext:
        """Build an analytics context from repository state."""

        return HistoricalAnalyticsContext(runs=self.runs, findings=self.findings)

    def list_runs(self) -> tuple[HistoricalRunEntry, ...]:
        """Return the repository's historical runs."""

        return self.runs

    def list_findings(self) -> tuple[HistoricalFindingEntry, ...]:
        """Return the repository's historical findings."""

        return self.findings
