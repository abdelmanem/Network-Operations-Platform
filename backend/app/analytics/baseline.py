"""Baseline comparison helpers for historical analytics."""

from __future__ import annotations

from backend.app.analytics.context import HistoricalRunEntry
from backend.app.analytics.metadata import BaselineComparison, BaselineDirection


def compare_to_baseline(
    current: HistoricalRunEntry,
    baseline: HistoricalRunEntry,
    *,
    direction: BaselineDirection,
) -> BaselineComparison:
    """Compare the current run against a baseline run."""

    compliance_delta = float(current.compliance_score) - float(
        baseline.compliance_score
    )
    risk_delta = float(current.risk_score or 0.0) - float(baseline.risk_score or 0.0)
    return BaselineComparison(
        direction=direction,
        current_run_id=current.run_id,
        baseline_run_id=baseline.run_id,
        compliance_delta=compliance_delta,
        risk_delta=risk_delta,
    )
