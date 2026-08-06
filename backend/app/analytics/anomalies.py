"""Anomaly detection helpers for historical analytics."""

from __future__ import annotations

from backend.app.analytics.models import AnalyticsAnomaly


def detect_anomalies(
    risk_values: list[float | int],
    compliance_values: list[float | int],
) -> tuple[AnalyticsAnomaly, ...]:
    """Flag notable deviations in historical risk/compliance sequences."""

    anomalies: list[AnalyticsAnomaly] = []
    if len(risk_values) >= 2:
        latest_risk = float(risk_values[-1])
        prior_risk = float(risk_values[-2])
        risk_delta = latest_risk - prior_risk
        if abs(risk_delta) > 0.2:
            anomalies.append(
                AnalyticsAnomaly(
                    title="Risk swing",
                    severity="high",
                    details="Risk score changed materially between the latest runs.",
                    score=risk_delta,
                )
            )

    if len(compliance_values) >= 2:
        latest_compliance = float(compliance_values[-1])
        prior_compliance = float(compliance_values[-2])
        compliance_delta = latest_compliance - prior_compliance
        if abs(compliance_delta) > 8:
            anomalies.append(
                AnalyticsAnomaly(
                    title="Compliance swing",
                    severity="medium",
                    details="Compliance score changed materially in the latest run.",
                    score=compliance_delta,
                )
            )

    return tuple(anomalies)
