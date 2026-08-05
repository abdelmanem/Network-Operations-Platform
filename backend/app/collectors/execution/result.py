"""Collector execution result model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID

from backend.app.collectors.execution.progress import CollectorExecutionProgress
from backend.app.collectors.execution.status import CollectorExecutionStatus
from backend.app.discovery.context import DiscoveryTarget
from backend.app.snapshot.entities import InventorySnapshot


@dataclass(frozen=True, slots=True)
class CollectorExecutionResult:
    """Immutable result emitted by the collector runtime."""

    job_id: UUID
    collector_name: str
    target: DiscoveryTarget
    status: CollectorExecutionStatus
    snapshot: InventorySnapshot | None = None
    transport_name: str | None = None
    parser_name: str | None = None
    attempts: int = 0
    progress: CollectorExecutionProgress = field(
        default_factory=CollectorExecutionProgress.initial
    )
    error_message: str | None = None
    error_type: str | None = None
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def duration_seconds(self) -> float:
        """Return the execution duration in seconds."""

        return max(0.0, (self.finished_at - self.started_at).total_seconds())
