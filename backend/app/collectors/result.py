"""Collector result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryTarget
from backend.app.snapshot.entities import InventorySnapshot


@dataclass(frozen=True, slots=True)
class CollectorResult:
    """Result produced by a collector."""

    collector_name: str
    target: DiscoveryTarget
    snapshot: InventorySnapshot
    raw_payload: dict[str, object] = field(default_factory=dict)
    capabilities: frozenset[CollectorCapability] = field(default_factory=frozenset)
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
