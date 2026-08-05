"""Historical timeline queries."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.persistence.models import ComparisonResultRecord, DiscoveryRunRecord
from backend.app.persistence.repositories import HistoryRepository


@dataclass(slots=True)
class HistoryTimeline:
    """Read chronological immutable history."""

    repository: HistoryRepository

    def list(self) -> tuple[DiscoveryRunRecord | ComparisonResultRecord, ...]:
        """Return timeline records ordered newest first."""

        return self.repository.timeline()
