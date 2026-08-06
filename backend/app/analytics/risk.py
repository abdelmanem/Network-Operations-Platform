"""Risk analytics helpers for immutable historical analytics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from backend.app.analytics.context import HistoricalFindingEntry, HistoricalRunEntry
from backend.app.analytics.metadata import RiskAnalysis


def calculate_risk_analysis(
    runs: Iterable[HistoricalRunEntry],
    findings: Iterable[HistoricalFindingEntry],
) -> RiskAnalysis:
    """Calculate a compact risk profile from historical runs and findings."""

    run_list = tuple(runs)
    finding_list = tuple(findings)
    if not run_list:
        return RiskAnalysis(
            risk_delta=0.0,
            severity_movement={},
            risk_concentration=0.0,
            top_recurring_findings=(),
            unstable_devices=(),
            unstable_platforms=(),
        )

    latest = run_list[-1]
    previous = run_list[-2] if len(run_list) > 1 else run_list[0]
    severity_counts = Counter(finding.severity.lower() for finding in finding_list)
    recurring_titles = Counter(
        finding.title for finding in finding_list if finding.title
    )
    unstable_devices = tuple(
        sorted(
            {finding.device_id for finding in finding_list if finding.device_id},
            key=str,
        )
    )
    unstable_platforms = tuple(
        sorted(
            {finding.platform for finding in finding_list if finding.platform},
            key=str,
        )
    )
    return RiskAnalysis(
        risk_delta=float(latest.risk_score or 0.0) - float(previous.risk_score or 0.0),
        severity_movement=dict(severity_counts),
        risk_concentration=float(len(finding_list) / max(len(run_list), 1)),
        top_recurring_findings=tuple(
            sorted(recurring_titles.items(), key=lambda item: (-item[1], item[0]))[:3]
        ),
        unstable_devices=unstable_devices,
        unstable_platforms=unstable_platforms,
    )
