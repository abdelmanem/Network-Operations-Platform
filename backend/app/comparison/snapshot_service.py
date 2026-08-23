"""Compare existing immutable NetBox and live snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.comparison.engine import ComparisonEngine
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.persistence.models import DiscoveryRunRecord, SnapshotSource
from backend.app.persistence.repositories import FindingRepository, SnapshotRepository
from backend.app.snapshot.mapper import SnapshotMapper
from backend.app.snapshot.models import InventorySnapshotModel


class SnapshotComparisonError(ValueError):
    """Raised when requested snapshots cannot be compared safely."""


@dataclass(slots=True)
class SnapshotComparisonService:
    """Run the established comparison pipeline over durable snapshots."""

    session: Session
    comparison_engine: ComparisonEngine = field(default_factory=ComparisonEngine)
    snapshot_mapper: SnapshotMapper = field(default_factory=SnapshotMapper)

    def compare(
        self,
        *,
        expected_snapshot_id: UUID,
        observed_snapshot_id: UUID,
        tenant_id: str,
    ) -> UUID:
        """Persist a comparison result for tenant-owned live state and NetBox state."""

        snapshots = SnapshotRepository(self.session)
        expected = snapshots.get(expected_snapshot_id)
        observed = snapshots.get(observed_snapshot_id)
        if expected is None or observed is None:
            raise SnapshotComparisonError("Requested snapshot was not found.")
        if expected.source != SnapshotSource.NETBOX.value:
            raise SnapshotComparisonError(
                "Expected snapshot must have source 'netbox'."
            )
        if observed.source != SnapshotSource.LIVE.value:
            raise SnapshotComparisonError("Observed snapshot must have source 'live'.")
        if observed.discovery_run_id is None:
            raise SnapshotComparisonError(
                "Observed live snapshot is not tenant-scoped."
            )

        run = self.session.get(DiscoveryRunRecord, observed.discovery_run_id)
        if run is None or run.tenant_id != tenant_id:
            raise SnapshotComparisonError(
                "Observed snapshot is not available to this tenant."
            )

        try:
            expected_inventory = NetBoxInventorySnapshot.model_validate(
                expected.payload
            )
            observed_inventory = self.snapshot_mapper.to_entity(
                InventorySnapshotModel.model_validate(observed.payload)
            )
        except ValueError as exc:
            raise SnapshotComparisonError(
                "Requested snapshot payload is invalid."
            ) from exc

        result = self.comparison_engine.compare(expected_inventory, observed_inventory)
        record = FindingRepository(self.session).add_comparison_result(
            result,
            expected_snapshot_id=expected.id,
            observed_snapshot_id=observed.id,
        )
        self.session.commit()
        return record.id
