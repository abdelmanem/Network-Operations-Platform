"""Collector runtime context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryTarget
from backend.app.parsers.context import ParserInputFormat
from backend.app.transports.base import TransportCapability


@dataclass(slots=True)
class CollectorRuntimeContext:
    """Execution context for collector runtime jobs."""

    target: DiscoveryTarget
    required_capabilities: frozenset[CollectorCapability] = field(
        default_factory=frozenset
    )
    preferred_collector_name: str | None = None
    preferred_transport_name: str | None = None
    parser_name: str | None = None
    parser_input_format: ParserInputFormat = ParserInputFormat.JSON
    max_attempts: int = 1
    timeout_seconds: float | None = None
    retry_delay_seconds: float = 0.0
    metadata: dict[str, object] = field(default_factory=dict)
    run_id: UUID = field(default_factory=uuid4)
    correlation_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def build_collector_context(
        self,
        collector: BaseCollector,
        *,
        transport_name: str | None = None,
        transport_capabilities: frozenset[TransportCapability] = frozenset(),
    ) -> CollectorContext:
        """Convert runtime state into a collector execution context."""

        context_metadata = dict(self.metadata)
        if transport_name is not None:
            context_metadata["transport_name"] = transport_name
        if transport_capabilities:
            context_metadata["transport_capabilities"] = tuple(
                capability.value for capability in transport_capabilities
            )
        if self.parser_name is not None:
            context_metadata["parser_name"] = self.parser_name
        context_metadata["run_id"] = str(self.run_id)
        if self.correlation_id is not None:
            context_metadata["correlation_id"] = self.correlation_id

        return CollectorContext(
            target=self.target,
            capabilities=collector.capabilities,
            run_id=self.run_id,
            discovered_at=self.created_at,
            metadata=context_metadata,
        )
