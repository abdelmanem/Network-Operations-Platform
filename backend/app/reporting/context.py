"""Report generation context from cached immutable history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from backend.app.comparison.result import InventoryComparisonResult
from backend.app.evaluation.context import EvaluationDecision
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.snapshot.entities import InventorySnapshot as LiveInventorySnapshot


@dataclass(frozen=True, slots=True)
class DiscoveryRunSnapshot:
    """Immutable discovery run metrics from cached history."""

    run_id: UUID
    total_targets: int
    successful_targets: int
    failed_targets: int
    skipped_targets: int
    started_at: datetime
    finished_at: datetime | None = None
    target_identifier: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalRunSnapshot:
    """Immutable historical run entry for trend reporting."""

    run_id: UUID
    captured_at: datetime
    total_devices: int
    missing_devices: int
    extra_devices: int
    changed_devices: int
    compliance_score: int | None = None
    critical_findings: int = 0
    major_findings: int = 0
    minor_findings: int = 0


@dataclass(frozen=True, slots=True)
class ReportContext:
    """Cached inputs for report generation.

    The reporting engine consumes immutable cached history only and never
    recollects devices, reruns comparison, or reruns compliance evaluation.
    """

    netbox_inventory: NetBoxInventorySnapshot | None = None
    live_snapshot: LiveInventorySnapshot | None = None
    comparison_result: InventoryComparisonResult | None = None
    evaluation_decision: EvaluationDecision | None = None
    discovery_run: DiscoveryRunSnapshot | None = None
    historical_runs: tuple[HistoricalRunSnapshot, ...] = field(default_factory=tuple)
    run_id: UUID | None = None
    job_id: UUID | None = None
    site: str | None = None
    device_role: str | None = None
    platform: str | None = None
