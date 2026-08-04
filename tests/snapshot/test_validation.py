from datetime import UTC, datetime, timedelta

import pytest
from backend.app.snapshot.entities import DeviceSnapshot, InventorySnapshot
from backend.app.snapshot.mapper import SnapshotMapper
from backend.app.snapshot.validation import (
    SnapshotValidationError,
    validate_snapshot_integrity,
    validate_timestamp,
)


def test_validate_timestamp_rejects_future_values() -> None:
    with pytest.raises(SnapshotValidationError):
        validate_timestamp(
            datetime.now(UTC) + timedelta(days=1),
            context="snapshot timestamp",
        )


def test_validate_snapshot_integrity_rejects_duplicate_devices() -> None:
    snapshot = InventorySnapshot(
        devices=(
            DeviceSnapshot(device_id="device-1", name="Switch 1"),
            DeviceSnapshot(device_id="device-1", name="Switch 2"),
        ),
        captured_at=datetime.now(UTC),
    )

    model = SnapshotMapper().to_model(snapshot)

    with pytest.raises(SnapshotValidationError):
        validate_snapshot_integrity(model)
