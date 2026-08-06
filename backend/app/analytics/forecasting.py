"""Deterministic forecasting helpers for historical analytics."""

from __future__ import annotations

from collections.abc import Iterable


def moving_average(
    values: Iterable[float | int],
    *,
    window: int = 2,
) -> tuple[float, ...]:
    """Return a moving-average series for the supplied values."""

    series = [float(value) for value in values]
    if not series:
        return ()
    if window <= 0:
        window = 1
    result: list[float] = []
    for index in range(len(series)):
        start = max(0, index - window + 1)
        result.append(sum(series[start : index + 1]) / (index - start + 1))
    return tuple(result)


def linear_projection(
    values: Iterable[float | int],
    *,
    horizon: int = 1,
) -> tuple[float, ...]:
    """Project a simple linear trend over the supplied values."""

    series = [float(value) for value in values]
    if len(series) < 2:
        return tuple(series)

    slope = (series[-1] - series[0]) / max(len(series) - 1, 1)
    result = [series[-1] + slope * offset for offset in range(1, horizon + 1)]
    return tuple(result)


def trend_projection(
    values: Iterable[float | int],
    *,
    horizon: int = 1,
) -> tuple[float, ...]:
    """Project the overall trend using the latest delta."""

    series = [float(value) for value in values]
    if not series:
        return ()
    if len(series) < 2:
        return tuple(series)

    delta = series[-1] - series[-2]
    return tuple(series[-1] + delta * offset for offset in range(1, horizon + 1))
