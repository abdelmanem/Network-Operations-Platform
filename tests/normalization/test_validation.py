from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from backend.app.normalization.validator import NormalizationValidator
from backend.app.parsers.context import ParserInputFormat
from backend.app.parsers.exceptions import ParserValidationError
from backend.app.parsers.result import ParsedRecord, ParserResult
from backend.app.snapshot.entities import DeviceSnapshot, InventorySnapshot


def test_normalization_validator_rejects_naive_timestamps() -> None:
    result = ParserResult(
        parser_name="parser-1",
        source="console",
        input_format=ParserInputFormat.TEXT,
        records=(ParsedRecord(kind="device", payload={"device_id": "device-1"}),),
        captured_at=datetime.now(),
    )

    with pytest.raises(ParserValidationError):
        NormalizationValidator().validate_parsed_result(result)


def test_normalization_validator_rejects_empty_results() -> None:
    result = ParserResult(
        parser_name="parser-1",
        source="console",
        input_format=ParserInputFormat.TEXT,
        records=(),
        captured_at=datetime.now(UTC),
    )

    with pytest.raises(ParserValidationError):
        NormalizationValidator().validate_parsed_result(result)


def test_normalization_validator_rejects_duplicate_devices() -> None:
    snapshot = InventorySnapshot(
        devices=(
            DeviceSnapshot(device_id="device-1", name="Switch 1"),
            DeviceSnapshot(device_id="device-1", name="Switch 2"),
        ),
        captured_at=datetime.now(UTC),
    )

    with pytest.raises(ParserValidationError):
        NormalizationValidator().validate_snapshot(snapshot)


def test_normalization_validator_rejects_future_timestamps() -> None:
    result = ParserResult(
        parser_name="parser-1",
        source="console",
        input_format=ParserInputFormat.TEXT,
        records=(ParsedRecord(kind="device", payload={"device_id": "device-1"}),),
        captured_at=datetime.now(UTC) + timedelta(days=1),
    )

    with pytest.raises(ParserValidationError):
        NormalizationValidator().validate_parsed_result(result)
