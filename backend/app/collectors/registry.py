"""Collector registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from backend.app.collectors.base import BaseCollector
from backend.app.discovery.capabilities import CollectorCapability


@dataclass(slots=True)
class CollectorRegistry:
    """Register and resolve collectors."""

    _collectors: dict[str, BaseCollector] = field(default_factory=dict)

    def register(self, collector: BaseCollector | Callable[[], BaseCollector]) -> None:
        """Register a collector instance or factory."""

        if isinstance(collector, BaseCollector):
            self._collectors[collector.name] = collector
            return

        instance = collector()
        self._collectors[instance.name] = instance

    def register_alias(self, alias: str, name: str) -> None:
        """Register an alternate name for an existing collector."""

        if alias in self._collectors:
            raise ValueError(f"Collector alias '{alias}' is already registered.")
        self._collectors[alias] = self.get(name)

    def get(self, name: str) -> BaseCollector:
        """Return a collector by name."""

        try:
            return self._collectors[name]
        except KeyError as exc:
            raise KeyError(f"Unknown collector: {name}") from exc

    def select(
        self, capabilities: frozenset[CollectorCapability]
    ) -> tuple[BaseCollector, ...]:
        """Return collectors that satisfy the requested capabilities."""

        return tuple(
            collector
            for collector in self._collectors.values()
            if capabilities.issubset(collector.capabilities)
        )

    def names(self) -> tuple[str, ...]:
        """Return registered collector names."""

        return tuple(self._collectors)
