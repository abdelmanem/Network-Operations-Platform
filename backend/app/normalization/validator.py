"""Normalization validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from backend.app.parsers.exceptions import ParserValidationError
from backend.app.parsers.result import ParserResult
from backend.app.snapshot.entities import InventorySnapshot


@dataclass(slots=True)
class NormalizationValidator:
    """Validate parser output and normalized snapshots."""

    allow_empty_records: bool = False

    def validate_parsed_result(self, result: ParserResult) -> None:
        """Validate a parser result."""

        if result.captured_at.tzinfo is None:
            raise ParserValidationError(
                "Parser result timestamp must be timezone-aware."
            )

        if result.captured_at > datetime.now(UTC) + timedelta(seconds=1):
            raise ParserValidationError(
                "Parser result timestamp cannot be in the future."
            )

        if not self.allow_empty_records and not result.records:
            raise ParserValidationError(
                "Parser result must contain at least one record."
            )

    def validate_snapshot(self, snapshot: InventorySnapshot) -> None:
        """Validate a normalized snapshot."""

        seen_device_ids: set[str] = set()
        for device in snapshot.devices:
            if not device.device_id.strip():
                raise ParserValidationError(
                    "Normalized snapshot contains an empty device id."
                )
            if device.device_id in seen_device_ids:
                raise ParserValidationError(
                    "Normalized snapshot contains duplicate device id: "
                    f"{device.device_id}"
                )
            seen_device_ids.add(device.device_id)
