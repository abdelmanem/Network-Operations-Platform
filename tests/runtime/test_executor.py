from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.execution.exceptions import (
    CollectorExecutionCancelledError,
    CollectorExecutionTimeoutError,
)
from backend.app.collectors.execution.status import CollectorExecutionStatus
from backend.app.collectors.registry import CollectorRegistry
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.executor import CollectorExecutor
from backend.app.collectors.runtime.metrics import CollectorRuntimeMetrics
from backend.app.collectors.runtime.scheduler import CollectorScheduler
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryTarget
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.base import BaseParser
from backend.app.parsers.context import ParserContext, ParserInputFormat
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.registry import ParserRegistry
from backend.app.parsers.result import ParsedRecord, ParserResult
from backend.app.snapshot.entities import InventorySnapshot
from backend.app.snapshot.models import InventorySnapshotModel
from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
)
from backend.app.transports.manager import TransportManager
from backend.app.transports.session import TransportSession


class InMemorySnapshotRepository:
    def __init__(self) -> None:
        self.saved: list[InventorySnapshotModel] = []

    async def save(self, snapshot: InventorySnapshotModel) -> None:
        self.saved.append(snapshot)

    async def get(self, snapshot_id: UUID) -> InventorySnapshotModel | None:
        return None

    async def list(self) -> tuple[InventorySnapshotModel, ...]:
        return tuple(self.saved)

    async def delete(self, snapshot_id: UUID) -> None:
        return None

    async def clear(self) -> None:
        self.saved.clear()


@dataclass(slots=True)
class DummySession(TransportSession):
    async def close(self) -> None:
        self.mark_closed()


class DummyTransport(BaseTransport):
    name = "dummy-transport"
    capabilities = frozenset({TransportCapability.SSH})

    def health_check(self, context: TransportContext) -> None:
        return None

    def create_session(self, context: TransportContext) -> TransportSession:
        return DummySession(session_id=context.target.identifier)

    def close(self) -> None:
        return None


class DummyCollector(BaseCollector):
    name = "dummy-collector"
    capabilities = frozenset({CollectorCapability.SSH, CollectorCapability.INTERFACES})

    def __init__(self) -> None:
        self.invocations = 0

    async def health_check(self, context: CollectorContext) -> None:
        return None

    async def discover(self, context: CollectorContext) -> tuple[DiscoveryTarget, ...]:
        return ()

    async def collect(
        self,
        context: CollectorContext,
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> dict[str, object]:
        self.invocations += 1
        return {"device_id": context.target.identifier, "name": "Switch 1"}

    async def normalize(
        self,
        context: CollectorContext,
        raw_payload: dict[str, object],
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> InventorySnapshot:
        return InventorySnapshot.empty()

    async def close(self) -> None:
        return None


class FlakyCollector(DummyCollector):
    async def collect(
        self,
        context: CollectorContext,
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> dict[str, object]:
        self.invocations += 1
        if self.invocations == 1:
            raise RuntimeError("temporary failure")
        return {"device_id": context.target.identifier, "name": "Switch 1"}


class SlowCollector(DummyCollector):
    async def collect(
        self,
        context: CollectorContext,
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> dict[str, object]:
        import asyncio

        await asyncio.sleep(0.05)
        return await super().collect(context, discovered_targets=discovered_targets)


class DummyParser(BaseParser):
    def parse(self, context: ParserContext, raw_output: object) -> ParserResult:
        payload = dict(raw_output)
        return ParserResult(
            parser_name=self.name,
            source=context.source,
            input_format=context.input_format,
            records=(ParsedRecord(kind="device", payload=payload),),
        )


def build_executor(
    collector: BaseCollector,
) -> tuple[CollectorExecutor, InMemorySnapshotRepository]:
    collector_registry = CollectorRegistry()
    collector_registry.register(collector)
    transport_manager = TransportManager()
    transport_manager.register(DummyTransport())
    parser_registry = ParserRegistry()
    parser_registry.register(
        DummyParser(
            name="dummy-parser",
            supported_formats=frozenset({ParserInputFormat.JSON}),
        )
    )
    repository = InMemorySnapshotRepository()
    executor = CollectorExecutor(
        collector_registry=collector_registry,
        transport_manager=transport_manager,
        parser_pipeline=ParserPipeline(registry=parser_registry),
        normalization_engine=NormalizationEngine(),
        snapshot_repository=repository,
        metrics=CollectorRuntimeMetrics(),
    )
    return executor, repository


@pytest.mark.anyio
async def test_executor_runs_collector_and_persists_snapshot() -> None:
    executor, repository = build_executor(DummyCollector())
    job = await CollectorScheduler().schedule(
        CollectorRuntimeContext(
            target=DiscoveryTarget(identifier="device-1", address="10.0.0.1"),
            required_capabilities=frozenset({CollectorCapability.INTERFACES}),
            max_attempts=1,
        )
    )

    result = await executor.execute(job)

    assert result.status == CollectorExecutionStatus.SUCCEEDED
    assert result.snapshot is not None
    assert result.snapshot.devices[0].device_id == "device-1"
    assert len(repository.saved) == 1


@pytest.mark.anyio
async def test_executor_retries_transient_failures() -> None:
    executor, _ = build_executor(FlakyCollector())
    job = await CollectorScheduler().schedule(
        CollectorRuntimeContext(
            target=DiscoveryTarget(identifier="device-1", address="10.0.0.1"),
            required_capabilities=frozenset({CollectorCapability.INTERFACES}),
            max_attempts=2,
            retry_delay_seconds=0.0,
        )
    )

    result = await executor.execute(job)

    assert result.status == CollectorExecutionStatus.SUCCEEDED
    assert result.attempts == 2
    assert executor.metrics.retried == 1


@pytest.mark.anyio
async def test_executor_times_out_long_running_collector() -> None:
    executor, _ = build_executor(SlowCollector())
    job = await CollectorScheduler().schedule(
        CollectorRuntimeContext(
            target=DiscoveryTarget(identifier="device-1", address="10.0.0.1"),
            required_capabilities=frozenset({CollectorCapability.INTERFACES}),
            max_attempts=1,
            timeout_seconds=0.01,
        )
    )

    with pytest.raises(CollectorExecutionTimeoutError):
        await executor.execute(job)


@pytest.mark.anyio
async def test_executor_respects_job_cancellation() -> None:
    executor, _ = build_executor(DummyCollector())
    job = await CollectorScheduler().schedule(
        CollectorRuntimeContext(
            target=DiscoveryTarget(identifier="device-1", address="10.0.0.1"),
            required_capabilities=frozenset({CollectorCapability.INTERFACES}),
            max_attempts=1,
        )
    )
    job.cancel("stop")

    with pytest.raises(CollectorExecutionCancelledError):
        await executor.execute(job)
