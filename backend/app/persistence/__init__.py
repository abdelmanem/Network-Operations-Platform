"""Immutable persistence layer for discovery history."""

from backend.app.persistence.models import (
    ComparisonResultRecord,
    DiscoveryRunRecord,
    EvidenceRecord,
    FindingRecord,
    SnapshotDeviceRecord,
    SnapshotInterfaceRecord,
    SnapshotNeighborRecord,
    SnapshotRecord,
    SnapshotVLANRecord,
)
from backend.app.persistence.repositories import (
    FindingRepository,
    HistoryRepository,
    SnapshotRepository,
)
from backend.app.persistence.unit_of_work import PersistenceUnitOfWork

__all__ = [
    "ComparisonResultRecord",
    "DiscoveryRunRecord",
    "EvidenceRecord",
    "FindingRecord",
    "FindingRepository",
    "HistoryRepository",
    "PersistenceUnitOfWork",
    "SnapshotDeviceRecord",
    "SnapshotInterfaceRecord",
    "SnapshotNeighborRecord",
    "SnapshotRecord",
    "SnapshotRepository",
    "SnapshotVLANRecord",
]
