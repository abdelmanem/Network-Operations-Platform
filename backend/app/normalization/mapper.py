"""Normalization mapper."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from backend.app.parsers.result import ParserResult
from backend.app.snapshot.entities import (
    DeviceSnapshot,
    InterfaceSnapshot,
    InventorySnapshot,
    NeighborSnapshot,
    PowerSnapshot,
    VLANSnapshot,
)


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
                    product_id=self._optional_text(record.payload.get("product_id")),
                    management_ip=self._optional_text(
                        record.payload.get("management_ip")
                    ),
                    base_mac=self._optional_text(record.payload.get("base_mac")),
                    software_version=self._optional_text(
                        record.payload.get("software_version")
                    ),
                    uptime=self._optional_text(record.payload.get("uptime")),
                    hardware_revision=self._optional_text(
                        record.payload.get("hardware_revision")
                    ),
                    platform=self._optional_text(record.payload.get("platform")),
                    stack_members=self._stack_members(
                        record.payload.get("stack_members")
                    ),
                    interfaces=self._interfaces(result, device_id),
                    vlans=self._vlans(result, device_id),
                    neighbors=self._neighbors(result, device_id),
                    power=self._power(result, device_id),
                )
            )

        return InventorySnapshot(
            devices=tuple(devices),
            source=result.source,
            captured_at=result.captured_at,
        )

    def _interfaces(
        self,
        result: ParserResult,
        device_id: str,
    ) -> tuple[InterfaceSnapshot, ...]:
        interfaces: list[InterfaceSnapshot] = []
        for record in result.records:
            if record.kind != "interface":
                continue
            if str(record.payload.get("device_id", "")).strip() != device_id:
                continue

            name = str(record.payload.get("name", "")).strip()
            if not name:
                continue

            interfaces.append(
                InterfaceSnapshot(
                    device_id=device_id,
                    name=name,
                    admin_status=self._optional_text(
                        record.payload.get("admin_status")
                    ),
                    oper_status=self._optional_text(record.payload.get("oper_status")),
                    description=self._optional_text(record.payload.get("description")),
                    mac_address=self._optional_text(record.payload.get("mac_address")),
                    speed_mbps=self._optional_int(record.payload.get("speed_mbps")),
                    poe_status=self._optional_text(record.payload.get("poe_status")),
                )
            )
        return tuple(interfaces)

    def _vlans(self, result: ParserResult, device_id: str) -> tuple[VLANSnapshot, ...]:
        vlans: list[VLANSnapshot] = []
        for record in result.records:
            if record.kind != "vlan":
                continue
            if str(record.payload.get("device_id", "")).strip() != device_id:
                continue

            vlan_id = self._optional_int(record.payload.get("vlan_id"))
            name = str(record.payload.get("name", "")).strip()
            if vlan_id is None or not name:
                continue

            vlans.append(
                VLANSnapshot(
                    vlan_id=vlan_id,
                    name=name,
                    device_id=device_id,
                    status=self._optional_text(record.payload.get("status")),
                )
            )
        return tuple(vlans)

    def _neighbors(
        self,
        result: ParserResult,
        device_id: str,
    ) -> tuple[NeighborSnapshot, ...]:
        neighbors: list[NeighborSnapshot] = []
        for record in result.records:
            if record.kind != "neighbor":
                continue
            if str(record.payload.get("local_device_id", "")).strip() != device_id:
                continue

            local_interface = str(record.payload.get("local_interface", "")).strip()
            remote_device_id = str(record.payload.get("remote_device_id", "")).strip()
            if not local_interface or not remote_device_id:
                continue

            neighbors.append(
                NeighborSnapshot(
                    local_device_id=device_id,
                    local_interface=local_interface,
                    remote_device_id=remote_device_id,
                    remote_interface=self._optional_text(
                        record.payload.get("remote_interface")
                    ),
                    protocol=self._optional_text(record.payload.get("protocol")),
                )
            )
        return tuple(neighbors)

    def _power(self, result: ParserResult, device_id: str) -> PowerSnapshot | None:
        for record in result.records:
            if record.kind != "power":
                continue
            if str(record.payload.get("device_id", "")).strip() != device_id:
                continue

            return PowerSnapshot(
                device_id=device_id,
                source=str(record.payload.get("source", "poe")).strip() or "poe",
                status=self._optional_text(record.payload.get("status")),
                available_watts=self._optional_float(
                    record.payload.get("available_watts")
                ),
                consumed_watts=self._optional_float(
                    record.payload.get("consumed_watts")
                ),
                poe_enabled=self._optional_bool(record.payload.get("poe_enabled")),
            )
        return None

    @staticmethod
    def _optional_text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).strip())
        except ValueError:
            return None

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"true", "yes", "enabled", "on", "1"}:
            return True
        if normalized in {"false", "no", "disabled", "off", "0"}:
            return False
        return None

    @staticmethod
    def _stack_members(value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return (value.strip(),) if value.strip() else ()
        if not isinstance(value, Iterable):
            return ()
        return tuple(str(item).strip() for item in value if str(item).strip())
