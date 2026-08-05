"""Discovery run history queries."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.app.persistence.models import DiscoveryRunRecord
from backend.app.persistence.repositories import HistoryRepository


@dataclass(slots=True)
class DiscoveryHistory:
    """Read discovery run history."""

    repository: HistoryRepository

    def get(self, identity: UUID) -> DiscoveryRunRecord | None:
        """Return one discovery run."""

        return self.repository.get_discovery_run(identity)

    def list(self) -> tuple[DiscoveryRunRecord, ...]:
        """Return all discovery runs."""

        return self.repository.list_discovery_runs()
