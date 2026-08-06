"""Execution metrics for the job framework."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class JobMetrics:
    """Mutable metrics for job execution."""

    submitted_jobs: int = 0
    queued_jobs: int = 0
    started_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    timed_out_jobs: int = 0

    def record_submitted(self) -> None:
        self.submitted_jobs += 1

    def record_queued(self) -> None:
        self.queued_jobs += 1

    def record_started(self) -> None:
        self.started_jobs += 1

    def record_completed(self) -> None:
        self.completed_jobs += 1

    def record_failed(self) -> None:
        self.failed_jobs += 1

    def record_cancelled(self) -> None:
        self.cancelled_jobs += 1

    def record_timed_out(self) -> None:
        self.timed_out_jobs += 1
