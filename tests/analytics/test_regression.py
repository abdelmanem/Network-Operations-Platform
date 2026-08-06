from __future__ import annotations

from backend.app.analytics.regression import fit_linear_regression


def test_fit_linear_regression_returns_expected_slope_and_intercept() -> None:
    slope, intercept = fit_linear_regression([1, 2, 3], [2, 4, 6])

    assert slope == 2.0
    assert intercept == 0.0
