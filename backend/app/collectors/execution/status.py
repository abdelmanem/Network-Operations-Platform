"""Collector execution status models."""

from __future__ import annotations

from enum import StrEnum


class CollectorExecutionStatus(StrEnum):
    """Lifecycle states for collector execution."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
