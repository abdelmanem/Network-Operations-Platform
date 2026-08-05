"""Tests for transport diagnostics and metrics models."""

from __future__ import annotations

from backend.app.transports import TransportDiagnostic, TransportMetrics


def test_transport_diagnostic_serializes_state() -> None:
    diagnostic = TransportDiagnostic(
        transport_name="httpx",
        target_identifier="device-1",
        target_address="10.0.0.10",
        connected=True,
        detail="session-open",
    )

    payload = diagnostic.as_dict()

    assert payload["transport_name"] == "httpx"
    assert payload["connected"] is True
    assert payload["detail"] == "session-open"


def test_transport_metrics_records_counters() -> None:
    metrics = TransportMetrics()

    metrics.record_attempt()
    metrics.record_success()
    metrics.record_failure()

    payload = metrics.as_dict()

    assert payload["attempts"] == 1
    assert payload["successes"] == 1
    assert payload["failures"] == 1
    assert payload["opened_at"] is not None
