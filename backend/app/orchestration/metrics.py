"""Orchestration execution metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OrchestrationMetrics:
    """Mutable orchestration metrics."""

    submitted_runs: int = 0
    succeeded_runs: int = 0
    failed_runs: int = 0
    cancelled_runs: int = 0
    retried_runs: int = 0
    collector_jobs: int = 0
    persisted_records: int = 0
    duration_seconds: float = 0.0

    def snapshot(self) -> dict[str, int | float]:
        """Return a serializable metrics snapshot."""

        return {
            "submitted_runs": self.submitted_runs,
            "succeeded_runs": self.succeeded_runs,
            "failed_runs": self.failed_runs,
            "cancelled_runs": self.cancelled_runs,
            "retried_runs": self.retried_runs,
            "collector_jobs": self.collector_jobs,
            "persisted_records": self.persisted_records,
            "duration_seconds": self.duration_seconds,
        }
