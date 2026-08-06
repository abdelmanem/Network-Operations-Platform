"""Comparison helpers for analytics baselines and run-to-run drift."""

from __future__ import annotations

from backend.app.analytics.context import HistoricalRunEntry
from backend.app.analytics.metadata import ComparisonPoint


def build_comparison_points(
    runs: tuple[HistoricalRunEntry, ...],
) -> tuple[ComparisonPoint, ...]:
    """Create simple comparison points between consecutive runs."""

    points: list[ComparisonPoint] = []
    for previous, current in zip(runs, runs[1:], strict=False):
        points.append(
            ComparisonPoint(
                previous_run_id=previous.run_id,
                current_run_id=current.run_id,
                compliance_delta=float(current.compliance_score)
                - float(previous.compliance_score),
                risk_delta=float(current.risk_score or 0.0)
                - float(previous.risk_score or 0.0),
                discovered_delta=current.discovered_devices
                - previous.discovered_devices,
            )
        )
    return tuple(points)
