"""Collector runtime executor."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.execution.exceptions import (
    CollectorExecutionCancelledError,
    CollectorExecutionError,
    CollectorExecutionTimeoutError,
    CollectorNotFoundError,
    CollectorRetryExhaustedError,
    TransportSelectionError,
)
from backend.app.collectors.execution.result import CollectorExecutionResult
from backend.app.collectors.execution.status import CollectorExecutionStatus
from backend.app.collectors.registry import CollectorRegistry
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.job import CollectorJob
from backend.app.collectors.runtime.metrics import CollectorRuntimeMetrics
from backend.app.collectors.runtime.processing import process_collector_payload
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.snapshot.mapper import SnapshotMapper
from backend.app.snapshot.repository import SnapshotRepository
from backend.app.transports.base import TransportCapability, TransportTarget
from backend.app.transports.manager import TransportManager


@dataclass(slots=True)
class CollectorExecutor:
    """Execute collector jobs end to end."""

    collector_registry: CollectorRegistry
    transport_manager: TransportManager
    parser_pipeline: ParserPipeline
    normalization_engine: NormalizationEngine
    snapshot_repository: SnapshotRepository
    metrics: CollectorRuntimeMetrics = field(default_factory=CollectorRuntimeMetrics)
    snapshot_mapper: SnapshotMapper = field(default_factory=SnapshotMapper)

    async def execute(self, job: CollectorJob) -> CollectorExecutionResult:
        """Execute a collector job and persist the resulting snapshot."""

        if job.is_cancelled:
            raise CollectorExecutionCancelledError("Collector job was cancelled.")

        context = job.context
        collector = self._resolve_collector(context)
        transport_name, transport_capabilities = self._resolve_transport(
            collector,
            context,
        )
        max_attempts = max(1, context.max_attempts)
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            job.state.increment_attempts()
            job.state.mark_running()
            self.metrics.record_started()
            started_at = datetime.now(UTC)

            try:
                if context.timeout_seconds is None:
                    result = await self._run_once(
                        job=job,
                        collector=collector,
                        transport_name=transport_name,
                        transport_capabilities=transport_capabilities,
                        started_at=started_at,
                    )
                else:
                    result = await asyncio.wait_for(
                        self._run_once(
                            job=job,
                            collector=collector,
                            transport_name=transport_name,
                            transport_capabilities=transport_capabilities,
                            started_at=started_at,
                        ),
                        timeout=context.timeout_seconds,
                    )
            except asyncio.CancelledError as exc:
                job.cancel("Collector execution cancelled.")
                self.metrics.record_cancelled()
                raise CollectorExecutionCancelledError(
                    "Collector execution cancelled."
                ) from exc
            except CollectorExecutionCancelledError:
                job.state.mark_cancelled("Collector execution cancelled.")
                self.metrics.record_cancelled()
                raise
            except TimeoutError as exc:
                last_error = exc
                job.state.mark_timed_out(str(exc))
                self.metrics.record_timed_out()
                if attempt < max_attempts:
                    job.state.mark_retrying(message="Retrying after timeout.")
                    self.metrics.record_retry()
                    await self._sleep(context.retry_delay_seconds)
                    continue
                raise CollectorExecutionTimeoutError(
                    "Collector execution timed out."
                ) from exc
            except CollectorExecutionError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts:
                    job.state.mark_retrying(message=str(exc))
                    self.metrics.record_retry()
                    await self._sleep(context.retry_delay_seconds)
                    continue
                job.state.mark_failed(str(exc))
                self.metrics.record_failed()
                raise CollectorRetryExhaustedError(
                    "Collector execution retries were exhausted."
                ) from exc
            else:
                job.state.mark_succeeded()
                self.metrics.record_succeeded(result.duration_seconds)
                return result

        raise CollectorRetryExhaustedError(
            "Collector execution retries were exhausted."
        ) from last_error

    async def _run_once(
        self,
        *,
        job: CollectorJob,
        collector: BaseCollector,
        transport_name: str | None,
        transport_capabilities: frozenset[TransportCapability],
        started_at: datetime,
    ) -> CollectorExecutionResult:
        runtime_context = job.context
        collector_context: CollectorContext = runtime_context.build_collector_context(
            collector,
            transport_name=transport_name,
            transport_capabilities=transport_capabilities,
        )

        selected_transport_name = transport_name
        if selected_transport_name is not None:
            transport_target = TransportTarget(
                identifier=runtime_context.target.identifier,
                address=runtime_context.target.address,
                metadata=dict(runtime_context.target.metadata),
            )
            await self.transport_manager.open_session(
                selected_transport_name,
                transport_target,
                capabilities=transport_capabilities,
            )

        await collector.health_check(collector_context)
        raw_payload = await collector.collect(
            collector_context,
            discovered_targets=(),
        )
        processed = process_collector_payload(
            parser_pipeline=self.parser_pipeline,
            normalization_engine=self.normalization_engine,
            snapshot_mapper=self.snapshot_mapper,
            source=runtime_context.target.identifier,
            parser_name=runtime_context.parser_name,
            run_id=runtime_context.run_id,
            metadata=dict(runtime_context.metadata),
            raw_payload=raw_payload,
        )
        await self.snapshot_repository.save(processed.snapshot_model)

        finished_at = datetime.now(UTC)
        return CollectorExecutionResult(
            job_id=job.id,
            collector_name=collector.name,
            target=runtime_context.target,
            status=CollectorExecutionStatus.SUCCEEDED,
            snapshot=processed.normalized_result.snapshot,
            transport_name=selected_transport_name,
            parser_name=processed.parsed_result.parser_name,
            attempts=job.state.attempts,
            started_at=started_at,
            finished_at=finished_at,
            metadata=dict(runtime_context.metadata),
        )

    def _resolve_collector(self, context: CollectorRuntimeContext) -> BaseCollector:
        if context.preferred_collector_name is not None:
            try:
                return self.collector_registry.get(context.preferred_collector_name)
            except KeyError as exc:
                raise CollectorNotFoundError(
                    f"Unknown collector: {context.preferred_collector_name}"
                ) from exc

        collectors = self.collector_registry.select(context.required_capabilities)
        if not collectors:
            raise CollectorNotFoundError(
                "No collector matched the requested capabilities."
            )
        return collectors[0]

    def _resolve_transport(
        self,
        collector: BaseCollector,
        context: CollectorRuntimeContext,
    ) -> tuple[str | None, frozenset[TransportCapability]]:
        transport_capabilities = self._collector_transport_capabilities(collector)
        if context.preferred_transport_name is not None:
            try:
                transport = self.transport_manager.resolve(
                    context.preferred_transport_name
                )
            except KeyError as exc:
                raise TransportSelectionError(
                    f"Unknown transport: {context.preferred_transport_name}"
                ) from exc
            if not transport_capabilities.issubset(transport.capabilities):
                raise TransportSelectionError(
                    "Preferred transport does not satisfy collector requirements."
                )
            return transport.name, transport.capabilities

        if not transport_capabilities:
            return None, frozenset()

        transports = self.transport_manager.select(transport_capabilities)
        if not transports:
            raise TransportSelectionError(
                "No transport matched the collector capability requirements."
            )
        transport = transports[0]
        return transport.name, transport.capabilities

    @staticmethod
    def _collector_transport_capabilities(
        collector: BaseCollector,
    ) -> frozenset[TransportCapability]:
        capabilities: set[TransportCapability] = set()
        for capability in collector.capabilities:
            for transport_capability in TransportCapability:
                if transport_capability.value == capability.value:
                    capabilities.add(transport_capability)
        return frozenset(capabilities)

    @staticmethod
    async def _sleep(delay_seconds: float) -> None:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
