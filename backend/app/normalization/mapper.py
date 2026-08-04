"""Normalization mapper."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.parsers.result import ParserResult
from backend.app.snapshot.entities import DeviceSnapshot, InventorySnapshot


@dataclass(slots=True)
class NormalizationMapper:
    """Map parser records into immutable snapshot entities."""

    def to_snapshot(self, result: ParserResult) -> InventorySnapshot:
        """Convert parser output into a canonical inventory snapshot."""

        devices: list[DeviceSnapshot] = []
        for record in result.records:
            if record.kind != "device":
                continue

            device_id = str(record.payload.get("device_id", "")).strip()
            name = str(record.payload.get("name", "")).strip()
            devices.append(
                DeviceSnapshot(
                    device_id=device_id,
                    name=name,
                    manufacturer=self._optional_text(
                        record.payload.get("manufacturer")
                    ),
                    model=self._optional_text(record.payload.get("model")),
                    serial_number=self._optional_text(
                        record.payload.get("serial_number")
                    ),
                    platform=self._optional_text(record.payload.get("platform")),
                )
            )

        return InventorySnapshot(
            devices=tuple(devices),
            source=result.source,
            captured_at=result.captured_at,
        )

    @staticmethod
    def _optional_text(value: object) -> str | None:
        text = str(value).strip()
        return text if text else None
