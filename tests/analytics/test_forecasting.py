from __future__ import annotations

from backend.app.analytics.forecasting import (
    linear_projection,
    moving_average,
    trend_projection,
)


def test_forecasting_helpers_are_deterministic() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    assert moving_average(values, window=2)[-1] == 3.5
    assert linear_projection(values, horizon=2)[-1] == 6.0
    assert trend_projection(values, horizon=2)[-1] == 6.0
