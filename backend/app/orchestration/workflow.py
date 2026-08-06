"""End-to-end orchestration workflow executor."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from backend.app.comparison.engine import ComparisonEngine
from backend.app.comparison.result import InventoryComparisonResult
from backend.app.evaluation.context import EvaluationContext
from backend.app.evaluation.engine import EvaluationEngine
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.orchestration.coordinator import DiscoveryCoordinator
from backend.app.orchestration.events import (
    OrchestrationEventNames,
    progress_payload,
    run_event,
)
from backend.app.orchestration.jobs import OrchestrationJob
from backend.app.orchestration.metrics import OrchestrationMetrics
from backend.app.orchestration.progress import OrchestrationProgress
from backend.app.orchestration.results import OrchestrationResult
from backend.app.orchestration.state import OrchestrationStatus
from backend.app.persistence.unit_of_work import PersistenceUnitOfWork
from backend.app.snapshot.entities import InventorySnapshot as LiveInventorySnapshot


class InventoryServiceProtocol(Protocol):
    """Inventory service protocol consumed by orchestration."""

    async def synchronize(
        self,
        *,
        force_refresh: bool = False,
    ) -> NetBoxInventorySnapshot:
        """Synchronize NetBox inventory."""


UnitOfWorkFactory = Callable[[], PersistenceUnitOfWork]


class OrchestrationCancelledError(RuntimeError):
    """Raised when an orchestration run is cancelled."""


@dataclass(slots=True)
class WorkflowEngine:
    """Execute the complete NetBox-to-persistence workflow."""

    inventory_service: InventoryServiceProtocol
    discovery_coordinator: DiscoveryCoordinator
    comparison_engine: ComparisonEngine
    evaluation_engine: EvaluationEngine
    unit_of_work_factory: UnitOfWorkFactory
    metrics: OrchestrationMetrics = field(default_factory=OrchestrationMetrics)
    event_names: OrchestrationEventNames = field(
        default_factory=OrchestrationEventNames
    )

    async def execute(self, job: OrchestrationJob) -> OrchestrationResult:
        """Execute one orchestration job with retry and cancellation support."""

        self.metrics.submitted_runs += 1
        await self._publish(job, self.event_names.RUN_STARTED)
        max_attempts = max(1, job.context.max_attempts)
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            job.state.increment_attempts()
            job.state.mark_running()
            try:
                result = await self._run_once(job)
            except OrchestrationCancelledError as exc:
                job.state.mark_cancelled(str(exc))
                self.metrics.cancelled_runs += 1
                await self._publish(job, self.event_names.RUN_CANCELLED, error=str(exc))
                return OrchestrationResult.failed(
                    job_id=job.id,
                    run_id=job.context.run_id,
                    status=OrchestrationStatus.CANCELLED,
                    error_message=str(exc),
                    metrics=self.metrics,
                )
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    self.metrics.retried_runs += 1
                    job.state.mark_retrying(str(exc))
                    if job.context.retry_delay_seconds > 0:
                        await asyncio.sleep(job.context.retry_delay_seconds)
                    continue
                job.state.mark_failed(str(exc))
                self.metrics.failed_runs += 1
                await self._publish(job, self.event_names.RUN_FAILED, error=str(exc))
                return OrchestrationResult.failed(
                    job_id=job.id,
                    run_id=job.context.run_id,
                    status=OrchestrationStatus.FAILED,
                    error_message=str(exc),
                    metrics=self.metrics,
                )
            else:
                job.state.mark_succeeded()
                self.metrics.succeeded_runs += 1
                await self._publish(job, self.event_names.RUN_SUCCEEDED)
                return result
        error_message = "Run failed." if last_error is None else str(last_error)
        return OrchestrationResult.failed(
            job_id=job.id,
            run_id=job.context.run_id,
            status=OrchestrationStatus.FAILED,
            error_message=error_message,
            metrics=self.metrics,
        )

    async def _run_once(self, job: OrchestrationJob) -> OrchestrationResult:
        started_at = job.state.started_at
        netbox_inventory = await self._step_async(
            job,
            "netbox_inventory",
            1,
            lambda: self.inventory_service.synchronize(
                force_refresh=job.context.force_netbox_refresh
            ),
        )
        live_snapshot = await self._step_async(
            job,
            "collector_runtime",
            2,
            lambda: self.discovery_coordinator.collect(job.context.collector_contexts),
        )
        live_inventory, collector_results = live_snapshot
        self.metrics.collector_jobs += len(collector_results)
        comparison_result = await self._step_sync(
            job,
            "comparison",
            3,
            lambda: self.comparison_engine.compare(netbox_inventory, live_inventory),
        )
        evaluation_decision = await self._step_sync(
            job,
            "evaluation",
            4,
            lambda: self.evaluation_engine.evaluate(
                EvaluationContext(
                    comparison_result=comparison_result,
                    metadata=job.context.metadata,
                    exceptions=job.context.exceptions,
                ),
                job.context.policies,
            ),
        )
        persisted = await self._step_sync(
            job,
            "persistence",
            5,
            lambda: self._persist(
                job,
                netbox_inventory,
                live_inventory,
                comparison_result,
            ),
        )
        await self._progress(job, "completed", 6, "Run completed.")
        if started_at is not None and job.state.finished_at is not None:
            self.metrics.duration_seconds = max(
                0.0,
                (job.state.finished_at - started_at).total_seconds(),
            )
        return OrchestrationResult(
            job_id=job.id,
            run_id=job.context.run_id,
            status=OrchestrationStatus.SUCCEEDED,
            netbox_inventory=netbox_inventory,
            live_snapshot=live_inventory,
            comparison_result=comparison_result,
            evaluation_decision=evaluation_decision,
            discovery_run_id=persisted["discovery_run_id"],
            netbox_snapshot_id=persisted["netbox_snapshot_id"],
            live_snapshot_id=persisted["live_snapshot_id"],
            comparison_record_id=persisted["comparison_record_id"],
            metrics=self.metrics.snapshot(),
        )

    async def _step_async[T](
        self,
        job: OrchestrationJob,
        step: str,
        completed_steps: int,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        self._raise_if_cancelled(job)
        await self._progress(job, step, completed_steps - 1, f"Starting {step}.")
        value = await operation()
        self._raise_if_cancelled(job)
        await self._progress(job, step, completed_steps, f"Completed {step}.")
        return value

    async def _step_sync[T](
        self,
        job: OrchestrationJob,
        step: str,
        completed_steps: int,
        operation: Callable[[], T],
    ) -> T:
        self._raise_if_cancelled(job)
        await self._progress(job, step, completed_steps - 1, f"Starting {step}.")
        value = operation()
        self._raise_if_cancelled(job)
        await self._progress(job, step, completed_steps, f"Completed {step}.")
        return value

    def _persist(
        self,
        job: OrchestrationJob,
        netbox_inventory: NetBoxInventorySnapshot,
        live_inventory: LiveInventorySnapshot,
        comparison_result: InventoryComparisonResult,
    ) -> dict[str, UUID]:
        with self.unit_of_work_factory() as unit_of_work:
            discovery_run = unit_of_work.history.create_discovery_run(
                str(job.context.run_id),
                metadata=job.context.metadata,
            )
            netbox_snapshot = unit_of_work.snapshots.add_netbox_snapshot(
                netbox_inventory
            )
            live_snapshot = unit_of_work.snapshots.add_live_snapshot(
                live_inventory,
                discovery_run_id=discovery_run.id,
            )
            comparison_record = unit_of_work.findings.add_comparison_result(
                comparison_result,
                expected_snapshot_id=netbox_snapshot.id,
                observed_snapshot_id=live_snapshot.id,
            )
            self.metrics.persisted_records += 3 + len(comparison_record.findings)
            return {
                "discovery_run_id": discovery_run.id,
                "netbox_snapshot_id": netbox_snapshot.id,
                "live_snapshot_id": live_snapshot.id,
                "comparison_record_id": comparison_record.id,
            }

    async def _progress(
        self,
        job: OrchestrationJob,
        step: str,
        completed_steps: int,
        message: str,
    ) -> None:
        progress = OrchestrationProgress.create(
            step,
            completed_steps,
            6,
            message=message,
        )
        if job.context.progress_callback is not None:
            result = job.context.progress_callback(progress)
            from inspect import isawaitable

            if isawaitable(result):
                await result
        await self._publish(
            job,
            self.event_names.RUN_PROGRESS,
            **progress_payload(progress),
        )

    async def _publish(
        self,
        job: OrchestrationJob,
        name: str,
        **payload: object,
    ) -> None:
        if job.context.event_publisher is not None:
            await job.context.event_publisher.publish(run_event(name, job, **payload))

    @staticmethod
    def _raise_if_cancelled(job: OrchestrationJob) -> None:
        if job.context.cancellation_token.is_cancelled:
            raise OrchestrationCancelledError(
                job.context.cancellation_token.reason or "Run cancelled."
            )
