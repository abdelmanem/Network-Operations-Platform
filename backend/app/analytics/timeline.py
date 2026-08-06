"""Timeline generation helpers for historical analytics."""

from __future__ import annotations

from backend.app.analytics.context import HistoricalAnalyticsContext
from backend.app.analytics.metadata import TimelineEntry


def build_timeline(context: HistoricalAnalyticsContext) -> tuple[TimelineEntry, ...]:
    """Build a chronological timeline from persisted runs and findings."""

    entries: list[TimelineEntry] = []
    for run in context.runs:
        entries.append(
            TimelineEntry(
                kind="discovery",
                timestamp=run.started_at,
                label=f"Discovery run {run.run_id.hex[:8]}",
                value=float(run.compliance_score),
            )
        )
    for finding in context.findings:
        entries.append(
            TimelineEntry(
                kind="finding",
                timestamp=finding.created_at,
                label=finding.title,
                value=float(1 if finding.resolved else 0),
            )
        )
    return tuple(sorted(entries, key=lambda entry: entry.timestamp))
