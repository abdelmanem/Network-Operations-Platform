"""Collector execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryTarget


@dataclass(slots=True)
class CollectorContext:
    """Context passed to collectors during discovery."""

    target: DiscoveryTarget
    capabilities: frozenset[CollectorCapability] = field(default_factory=frozenset)
    run_id: UUID = field(default_factory=uuid4)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = field(default_factory=dict)
