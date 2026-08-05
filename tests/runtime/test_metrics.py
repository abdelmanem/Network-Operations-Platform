from __future__ import annotations

from backend.app.collectors.runtime.metrics import CollectorRuntimeMetrics


def test_runtime_metrics_track_success_rate() -> None:
    metrics = CollectorRuntimeMetrics()

    metrics.record_submitted()
    metrics.record_started()
    metrics.record_retry()
    metrics.record_succeeded(1.5)

    assert metrics.submitted == 1
    assert metrics.started == 1
    assert metrics.retried == 1
    assert metrics.succeeded == 1
    assert metrics.success_rate == 1.0
    assert metrics.total_duration_seconds == 1.5
