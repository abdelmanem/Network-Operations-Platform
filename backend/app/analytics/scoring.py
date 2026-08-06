"""Reusable scoring helpers for analytics recommendations and risk."""

from __future__ import annotations


def score_risk(value: float | int) -> float:
    """Return a normalized risk score."""

    return round(float(value), 3)
