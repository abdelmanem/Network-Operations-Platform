"""Inventory matching between NetBox inventory and live snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.inventory.entities import Device as NetBoxDevice
from backend.app.snapshot.entities import DeviceSnapshot
from backend.app.snapshot.entities import (
    InventorySnapshot as LiveInventorySnapshot,
)


@dataclass(frozen=True, slots=True)
class InventoryMatch:
    """Matched and unmatched inventory objects."""

    matched_devices: tuple[tuple[NetBoxDevice, DeviceSnapshot], ...]
    missing_devices: tuple[NetBoxDevice, ...]
    unexpected_devices: tuple[DeviceSnapshot, ...]
    duplicate_netbox_device_names: tuple[str, ...] = field(default_factory=tuple)
    duplicate_live_device_names: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class InventoryMatcher:
    """Match canonical NetBox devices to live device snapshots."""

    def match(
        self,
        netbox: NetBoxInventorySnapshot,
        live: LiveInventorySnapshot,
    ) -> InventoryMatch:
        """Match devices by normalized name, then serial number."""

        live_by_name = self._live_by_name(live.devices)
        duplicate_netbox_names = self._duplicates(
            self._normalize(device.name) for device in netbox.devices
        )
        duplicate_live_names = self._duplicates(
            self._normalize(device.name) for device in live.devices
        )

        matched: list[tuple[NetBoxDevice, DeviceSnapshot]] = []
        missing: list[NetBoxDevice] = []
        unexpected = list(live.devices)

        for netbox_device in netbox.devices:
            name_key = self._normalize(netbox_device.name)
            live_device = live_by_name.get(name_key)
            if live_device is None and netbox_device.serial:
                live_device = self._live_by_serial(live.devices, netbox_device.serial)
            if live_device is None:
                missing.append(netbox_device)
                continue
            matched.append((netbox_device, live_device))
            unexpected = [
                device
                for device in unexpected
                if device.device_id != live_device.device_id
            ]

        return InventoryMatch(
            matched_devices=tuple(matched),
            missing_devices=tuple(missing),
            unexpected_devices=tuple(unexpected),
            duplicate_netbox_device_names=duplicate_netbox_names,
            duplicate_live_device_names=duplicate_live_names,
        )

    @classmethod
    def _live_by_name(
        cls, devices: tuple[DeviceSnapshot, ...]
    ) -> dict[str, DeviceSnapshot]:
        return {cls._normalize(device.name): device for device in devices}

    @classmethod
    def _live_by_serial(
        cls,
        devices: tuple[DeviceSnapshot, ...],
        serial: str,
    ) -> DeviceSnapshot | None:
        serial_key = cls._normalize(serial)
        for device in devices:
            if cls._normalize(device.serial_number) == serial_key:
                return device
        return None

    @staticmethod
    def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if not value:
                continue
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        return tuple(sorted(duplicates))

    @staticmethod
    def _normalize(value: str | None) -> str:
        return "" if value is None else value.strip().casefold()
