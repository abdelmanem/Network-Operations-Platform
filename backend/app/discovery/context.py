"""Discovery execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.discovery.capabilities import CollectorCapability


@dataclass(frozen=True, slots=True)
class DiscoveryTarget:
    """Identify a network target to discover."""

    identifier: str
    address: str
    tenant_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    capabilities: frozenset[CollectorCapability] = field(default_factory=frozenset)


@dataclass(slots=True)
class DiscoveryContext:
    """Context shared across discovery pipeline steps."""

    target: DiscoveryTarget
    required_capabilities: frozenset[CollectorCapability] = field(
        default_factory=frozenset
    )
    pipeline_name: str = "default"
    run_id: UUID = field(default_factory=uuid4)
    correlation_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
