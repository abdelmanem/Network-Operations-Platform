"""Reusable regression helpers for analytics forecasting."""

from __future__ import annotations

from collections.abc import Iterable


def fit_linear_regression(
    xs: Iterable[float | int],
    ys: Iterable[float | int],
) -> tuple[float, float]:
    """Fit a simple linear regression and return slope and intercept."""

    x_values = [float(value) for value in xs]
    y_values = [float(value) for value in ys]
    if len(x_values) != len(y_values) or not x_values:
        return 0.0, 0.0
    if len(x_values) == 1:
        return 0.0, y_values[0]

    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    numerator = sum(
        (x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values, strict=True)
    )
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    if denominator == 0:
        return 0.0, y_mean
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    return slope, intercept
