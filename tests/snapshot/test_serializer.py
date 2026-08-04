from datetime import UTC, datetime

from backend.app.snapshot.entities import DeviceSnapshot, InventorySnapshot
from backend.app.snapshot.mapper import SnapshotMapper
from backend.app.snapshot.serializer import SnapshotSerializer


def test_snapshot_serializer_round_trips_inventory_snapshot() -> None:
    snapshot = InventorySnapshot(
        devices=(
            DeviceSnapshot(
                device_id="device-1",
                name="Switch 1",
                captured_at=datetime.now(UTC),
            ),
        ),
        captured_at=datetime.now(UTC),
    )

    mapper = SnapshotMapper()
    model = mapper.to_model(snapshot)
    serializer = SnapshotSerializer()

    payload = serializer.serialize(model)
    restored = serializer.deserialize(payload)

    assert restored.devices[0].device_id == "device-1"
    assert restored.devices[0].name == "Switch 1"
