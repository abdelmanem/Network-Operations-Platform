"""Discovery scheduling helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from backend.app.discovery.context import DiscoveryContext
from backend.app.discovery.engine import DiscoveryEngine, DiscoveryRunResult


@dataclass(slots=True)
class DiscoveryScheduler:
    """Schedule discovery runs over multiple contexts."""

    engine: DiscoveryEngine

    async def run(
        self,
        contexts: Sequence[DiscoveryContext],
    ) -> tuple[DiscoveryRunResult, ...]:
        """Execute discovery sequentially for the provided contexts."""

        results: list[DiscoveryRunResult] = []
        for context in contexts:
            results.append(await self.engine.run(context))
        return tuple(results)
