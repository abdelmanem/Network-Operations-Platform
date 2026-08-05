"""Finding history queries."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.persistence.models import FindingRecord
from backend.app.persistence.repositories import FindingRepository


@dataclass(slots=True)
class FindingHistory:
    """Read persisted finding history."""

    repository: FindingRepository

    def list(self) -> tuple[FindingRecord, ...]:
        """Return all findings."""

        return self.repository.list_findings()
