"""Inventory comparator implementations."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.comparison.diff import Difference
from backend.app.comparison.matcher import InventoryMatch
from backend.app.comparison.registry import DifferenceBuilder
from backend.app.inventory import entities as netbox_entities
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.snapshot.entities import (
    DeviceSnapshot,
    InterfaceSnapshot,
    NeighborSnapshot,
    VLANSnapshot,
)
from backend.app.snapshot.entities import (
    InventorySnapshot as LiveInventorySnapshot,
)


@dataclass(slots=True)
class IdentityComparator:
    """Compare identity-level inventory consistency."""

    builder: DifferenceBuilder = field(default_factory=DifferenceBuilder)

    def compare(self, match: InventoryMatch) -> tuple[Difference, ...]:
        """Return duplicate identity differences."""

        differences: list[Difference] = []
        for name in match.duplicate_netbox_device_names:
            differences.append(
                self.builder.duplicate(
                    "device",
                    name,
                    observed=name,
                    description=f"NetBox contains duplicate device identity {name}.",
                )
            )
        for name in match.duplicate_live_device_names:
            differences.append(
                self.builder.duplicate(
                    "device",
                    name,
                    observed=name,
                    description=(
                        f"Live snapshot contains duplicate device identity {name}."
                    ),
                )
            )
        return tuple(differences)


@dataclass(slots=True)
class DeviceComparator:
    """Compare NetBox devices with live device snapshots."""

    builder: DifferenceBuilder = field(default_factory=DifferenceBuilder)

    def compare(self, match: InventoryMatch) -> tuple[Difference, ...]:
        """Return device-level differences."""

        differences: list[Difference] = []
        for netbox_device in match.missing_devices:
            differences.append(
                self.builder.missing(
                    "device",
                    netbox_device.name,
                    expected=netbox_device.name,
                    description=f"NetBox device {netbox_device.name} is missing live.",
                )
            )
        for live_device in match.unexpected_devices:
            differences.append(
                self.builder.unexpected(
                    "device",
                    live_device.name,
                    observed=live_device.name,
                    description=(
                        f"Live device {live_device.name} is not present in NetBox."
                    ),
                )
            )
        for netbox_device, live_device in match.matched_devices:
            differences.extend(self._compare_matched_device(netbox_device, live_device))
        return tuple(differences)

    def _compare_matched_device(
        self,
        netbox_device: netbox_entities.Device,
        live_device: DeviceSnapshot,
    ) -> list[Difference]:
        differences: list[Difference] = []
        subject_id = netbox_device.name
        self._append_modified(
            differences,
            subject_id,
            "serial",
            netbox_device.serial,
            live_device.serial_number,
        )
        self._append_modified(
            differences,
            subject_id,
            "primary_ip",
            netbox_device.primary_ip,
            live_device.management_ip,
        )
        self._append_modified(
            differences,
            subject_id,
            "model",
            netbox_device.device_type.model,
            live_device.model,
        )
        return differences

    def _append_modified(
        self,
        differences: list[Difference],
        subject_id: str,
        field_name: str,
        expected: str | None,
        observed: str | None,
    ) -> None:
        expected_value = self._normalize(expected)
        observed_value = self._normalize(observed)
        if not expected_value or not observed_value or expected_value == observed_value:
            return
        differences.append(
            self.builder.modified(
                "device",
                subject_id,
                field_name,
                expected=expected,
                observed=observed,
            )
        )

    @staticmethod
    def _normalize(value: str | None) -> str:
        return "" if value is None else value.strip().casefold()


@dataclass(slots=True)
class PlatformComparator:
    """Compare platform and firmware family fields."""

    builder: DifferenceBuilder = field(default_factory=DifferenceBuilder)

    def compare(self, match: InventoryMatch) -> tuple[Difference, ...]:
        """Return platform differences for matched devices."""

        differences: list[Difference] = []
        for netbox_device, live_device in match.matched_devices:
            expected = (
                None if netbox_device.platform is None else netbox_device.platform.name
            )
            observed = live_device.platform
            if not self._matches(expected, observed):
                differences.append(
                    self.builder.modified(
                        "platform",
                        netbox_device.name,
                        "platform",
                        expected=expected,
                        observed=observed,
                    )
                )
        return tuple(differences)

    @staticmethod
    def _matches(expected: str | None, observed: str | None) -> bool:
        if expected is None or observed is None:
            return True
        return expected.strip().casefold() in observed.strip().casefold()


@dataclass(slots=True)
class InterfaceComparator:
    """Compare interface inventory."""

    builder: DifferenceBuilder = field(default_factory=DifferenceBuilder)

    def compare(self, match: InventoryMatch) -> tuple[Difference, ...]:
        """Return interface differences for matched devices."""

        differences: list[Difference] = []
        for netbox_device, live_device in match.matched_devices:
            netbox_interfaces = self._netbox_interfaces(netbox_device)
            live_interfaces = {
                self._normalize(interface.name): interface
                for interface in live_device.interfaces
            }
            for key, netbox_interface in netbox_interfaces.items():
                live_interface = live_interfaces.get(key)
                subject_id = f"{netbox_device.name}:{netbox_interface.name}"
                if live_interface is None:
                    differences.append(
                        self.builder.missing(
                            "interface",
                            subject_id,
                            expected=netbox_interface.name,
                            description=(
                                f"NetBox interface {subject_id} is missing live."
                            ),
                        )
                    )
                    continue
                differences.extend(
                    self._compare_interface(
                        subject_id, netbox_interface, live_interface
                    )
                )
            for key, live_interface in live_interfaces.items():
                if key not in netbox_interfaces:
                    differences.append(
                        self.builder.unexpected(
                            "interface",
                            f"{netbox_device.name}:{live_interface.name}",
                            observed=live_interface.name,
                            description=(
                                f"Live interface {live_interface.name} is not "
                                "in NetBox."
                            ),
                        )
                    )
        return tuple(differences)

    def _compare_interface(
        self,
        subject_id: str,
        netbox_interface: netbox_entities.Interface,
        live_interface: InterfaceSnapshot,
    ) -> list[Difference]:
        differences: list[Difference] = []
        expected_admin = "up" if netbox_interface.enabled else "down"
        if (
            live_interface.admin_status
            and live_interface.admin_status != expected_admin
        ):
            differences.append(
                self.builder.modified(
                    "interface",
                    subject_id,
                    "enabled",
                    expected=netbox_interface.enabled,
                    observed=live_interface.admin_status,
                )
            )
        self._append_field(
            differences,
            subject_id,
            "mac_address",
            netbox_interface.mac_address,
            live_interface.mac_address,
        )
        self._append_field(
            differences,
            subject_id,
            "description",
            netbox_interface.description,
            live_interface.description,
        )
        return differences

    def _append_field(
        self,
        differences: list[Difference],
        subject_id: str,
        field_name: str,
        expected: str | None,
        observed: str | None,
    ) -> None:
        if not expected or not observed:
            return
        if self._normalize(expected) == self._normalize(observed):
            return
        differences.append(
            self.builder.modified(
                "interface",
                subject_id,
                field_name,
                expected=expected,
                observed=observed,
            )
        )

    @classmethod
    def _netbox_interfaces(
        cls, device: netbox_entities.Device
    ) -> dict[str, netbox_entities.Interface]:
        return {
            cls._normalize(interface.name): interface for interface in device.interfaces
        }

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold()


@dataclass(slots=True)
class VLANComparator:
    """Compare VLAN inventory."""

    builder: DifferenceBuilder = field(default_factory=DifferenceBuilder)

    def compare(
        self,
        netbox: NetBoxInventorySnapshot,
        live: LiveInventorySnapshot,
    ) -> tuple[Difference, ...]:
        """Return VLAN differences."""

        netbox_vlans = {vlan.vid: vlan for vlan in netbox.vlans}
        live_vlans: dict[int, VLANSnapshot] = {}
        for device in live.devices:
            for vlan in device.vlans:
                live_vlans[vlan.vlan_id] = vlan

        differences: list[Difference] = []
        for vid, netbox_vlan in netbox_vlans.items():
            live_vlan = live_vlans.get(vid)
            if live_vlan is None:
                differences.append(
                    self.builder.missing(
                        "vlan",
                        str(vid),
                        expected=netbox_vlan.name,
                        description=f"NetBox VLAN {vid} is missing live.",
                    )
                )
                continue
            differences.extend(self._compare_vlan(netbox_vlan, live_vlan))
        for vid, live_vlan in live_vlans.items():
            if vid not in netbox_vlans:
                differences.append(
                    self.builder.unexpected(
                        "vlan",
                        str(vid),
                        observed=live_vlan.name,
                        description=f"Live VLAN {vid} is not present in NetBox.",
                    )
                )
        return tuple(differences)

    def _compare_vlan(
        self,
        netbox_vlan: netbox_entities.VLAN,
        live_vlan: VLANSnapshot,
    ) -> list[Difference]:
        differences: list[Difference] = []
        if netbox_vlan.name.strip().casefold() != live_vlan.name.strip().casefold():
            differences.append(
                self.builder.modified(
                    "vlan",
                    str(netbox_vlan.vid),
                    "name",
                    expected=netbox_vlan.name,
                    observed=live_vlan.name,
                )
            )
        if netbox_vlan.status and live_vlan.status:
            if (
                netbox_vlan.status.strip().casefold()
                != live_vlan.status.strip().casefold()
            ):
                differences.append(
                    self.builder.modified(
                        "vlan",
                        str(netbox_vlan.vid),
                        "status",
                        expected=netbox_vlan.status,
                        observed=live_vlan.status,
                    )
                )
        return differences


@dataclass(slots=True)
class NeighborComparator:
    """Compare neighbor inventory where NetBox data is unavailable."""

    builder: DifferenceBuilder = field(default_factory=DifferenceBuilder)

    def compare(self, live: LiveInventorySnapshot) -> tuple[Difference, ...]:
        """Return unsupported differences for observed live neighbors."""

        differences: list[Difference] = []
        for device in live.devices:
            for neighbor in device.neighbors:
                differences.append(self._unsupported_neighbor(device.name, neighbor))
        return tuple(differences)

    def _unsupported_neighbor(
        self,
        device_name: str,
        neighbor: NeighborSnapshot,
    ) -> Difference:
        return self.builder.unsupported(
            "neighbor",
            f"{device_name}:{neighbor.local_interface}:{neighbor.remote_device_id}",
            observed=neighbor.remote_device_id,
            description=(
                "Live neighbor was observed, but canonical NetBox neighbor "
                "inventory is not modeled yet."
            ),
        )
