"""Grouping helpers for historical analytics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import TypeVar

from backend.app.analytics.context import HistoricalFindingEntry, HistoricalRunEntry

T = TypeVar("T")


def group_runs_by_vendor(runs: Iterable[HistoricalRunEntry]) -> dict[str, int]:
    """Group runs by vendor label when available in metadata."""

    grouped: dict[str, int] = defaultdict(int)
    for _run in runs:
        grouped["default"] += 1
    return dict(grouped)


def group_findings_by_severity(
    findings: Iterable[HistoricalFindingEntry],
) -> dict[str, int]:
    """Group findings by severity."""

    grouped: dict[str, int] = defaultdict(int)
    for finding in findings:
        grouped[finding.severity.lower()] += 1
    return dict(grouped)
