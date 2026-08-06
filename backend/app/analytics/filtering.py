"""Filtering helpers for historical analytics."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from backend.app.analytics.context import HistoricalFindingEntry, HistoricalRunEntry


def filter_runs_by_date(
    runs: Iterable[HistoricalRunEntry],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[HistoricalRunEntry, ...]:
    """Filter runs by a date window."""

    selected = tuple(runs)
    if start is not None:
        selected = tuple(run for run in selected if run.started_at >= start)
    if end is not None:
        selected = tuple(run for run in selected if run.started_at <= end)
    return selected


def filter_findings_by_severity(
    findings: Iterable[HistoricalFindingEntry],
    severity: str,
) -> tuple[HistoricalFindingEntry, ...]:
    """Filter persisted findings by severity."""

    return tuple(
        finding for finding in findings if finding.severity.lower() == severity.lower()
    )
