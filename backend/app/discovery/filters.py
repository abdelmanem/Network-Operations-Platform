"""Reusable discovery filters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryContext


class DiscoveryFilter(Protocol):
    """Protocol for discovery filters."""

    def matches(self, context: DiscoveryContext) -> bool:
        """Return whether the context should be included."""


@dataclass(frozen=True, slots=True)
class CapabilityDiscoveryFilter:
    """Filter discovery contexts by required capabilities."""

    capabilities: frozenset[CollectorCapability]

    def matches(self, context: DiscoveryContext) -> bool:
        """Return whether the context matches the required capabilities."""

        return self.capabilities.issubset(
            context.required_capabilities | context.target.capabilities
        )


@dataclass(frozen=True, slots=True)
class AndDiscoveryFilter:
    """Logical AND filter composition."""

    filters: Sequence[DiscoveryFilter]

    def matches(self, context: DiscoveryContext) -> bool:
        """Return whether all nested filters match."""

        return all(filter_.matches(context) for filter_ in self.filters)


@dataclass(frozen=True, slots=True)
class OrDiscoveryFilter:
    """Logical OR filter composition."""

    filters: Sequence[DiscoveryFilter]

    def matches(self, context: DiscoveryContext) -> bool:
        """Return whether any nested filter matches."""

        return any(filter_.matches(context) for filter_ in self.filters)


@dataclass(frozen=True, slots=True)
class NotDiscoveryFilter:
    """Logical NOT filter composition."""

    filter: DiscoveryFilter

    def matches(self, context: DiscoveryContext) -> bool:
        """Return the inverse of the nested filter."""

        return not self.filter.matches(context)
