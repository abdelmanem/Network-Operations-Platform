from __future__ import annotations

from datetime import UTC, datetime

from backend.app.normalization.mapper import NormalizationMapper
from backend.app.parsers.context import ParserInputFormat
from backend.app.parsers.result import ParsedRecord, ParserResult


def test_normalization_mapper_maps_device_records_to_snapshot() -> None:
    result = ParserResult(
        parser_name="device-parser",
        source="console",
        input_format=ParserInputFormat.TEXT,
        records=(
            ParsedRecord(
                kind="device",
                payload={
                    "device_id": "device-1",
                    "name": "Switch 1",
                    "manufacturer": "Cisco",
                    "model": "WS-C2960X",
                    "serial_number": "ABC123",
                    "platform": "ios",
                },
            ),
            ParsedRecord(kind="ignored", payload={}),
        ),
        captured_at=datetime.now(UTC),
    )

    snapshot = NormalizationMapper().to_snapshot(result)

    assert snapshot.source == "console"
    assert len(snapshot.devices) == 1
    device = snapshot.devices[0]
    assert device.device_id == "device-1"
    assert device.name == "Switch 1"
    assert device.manufacturer == "Cisco"
