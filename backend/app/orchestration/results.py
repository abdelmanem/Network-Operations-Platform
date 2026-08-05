"""Orchestration result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from backend.app.comparison.result import InventoryComparisonResult
from backend.app.evaluation.context import EvaluationDecision
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.orchestration.metrics import OrchestrationMetrics
from backend.app.orchestration.state import OrchestrationStatus
from backend.app.snapshot.entities import InventorySnapshot as LiveInventorySnapshot


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    """Immutable final run result."""

    job_id: UUID
    run_id: UUID
    status: OrchestrationStatus
    netbox_inventory: NetBoxInventorySnapshot | None = None
    live_snapshot: LiveInventorySnapshot | None = None
    comparison_result: InventoryComparisonResult | None = None
    evaluation_decision: EvaluationDecision | None = None
    discovery_run_id: UUID | None = None
    netbox_snapshot_id: UUID | None = None
    live_snapshot_id: UUID | None = None
    comparison_record_id: UUID | None = None
    error_message: str | None = None
    metrics: dict[str, int | float] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def failed(
        cls,
        *,
        job_id: UUID,
        run_id: UUID,
        status: OrchestrationStatus,
        error_message: str,
        metrics: OrchestrationMetrics,
    ) -> OrchestrationResult:
        """Create a failed or cancelled result."""

        return cls(
            job_id=job_id,
            run_id=run_id,
            status=status,
            error_message=error_message,
            metrics=metrics.snapshot(),
        )
