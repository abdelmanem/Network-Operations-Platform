"""Trend classification helpers for analytics."""

from __future__ import annotations

from statistics import mean


def classify_trend(values: list[float | int]) -> str:
    """Classify a series as increasing, decreasing, stable, or volatile."""

    if len(values) < 2:
        return "stable"

    series = [float(value) for value in values]
    baseline = series[0]
    latest = series[-1]
    delta = latest - baseline
    average = mean(series)
    if average == 0:
        return "stable"

    volatility = sum(
        abs(series[index] - series[index - 1]) for index in range(1, len(series))
    )
    if volatility / max(len(series) - 1, 1) > max(0.1 * abs(average), 2.0):
        return "volatile"

    if abs(delta) <= max(1.0, abs(average) * 0.03):
        return "stable"
    if delta > 0:
        return "increasing"
    return "decreasing"


def calculate_finding_evolution(total_findings: int, resolved_findings: int) -> float:
    """Return a bounded evolution score based on resolution progress."""

    if total_findings <= 0:
        return 0.0
    return round(resolved_findings / total_findings, 3)
