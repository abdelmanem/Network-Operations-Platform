"""Snapshot mapping helpers."""

from __future__ import annotations

from dataclasses import asdict

from backend.app.snapshot import entities as entity_models
from backend.app.snapshot import models as snapshot_models


class SnapshotMapper:
    """Convert between snapshot entities and Pydantic models."""

    def to_model(
        self, snapshot: entity_models.InventorySnapshot
    ) -> snapshot_models.InventorySnapshotModel:
        """Convert an immutable entity into a Pydantic model."""

        return snapshot_models.InventorySnapshotModel.model_validate(asdict(snapshot))

    def to_entity(
        self, snapshot: snapshot_models.InventorySnapshotModel
    ) -> entity_models.InventorySnapshot:
        """Convert a Pydantic model into an immutable entity."""

        return entity_models.InventorySnapshot(
            devices=tuple(self._device_entity(device) for device in snapshot.devices),
            snapshot_id=snapshot.snapshot_id,
            captured_at=snapshot.captured_at,
            version=snapshot.version,
            source=snapshot.source,
        )

    def _device_entity(
        self, snapshot: snapshot_models.DeviceSnapshotModel
    ) -> entity_models.DeviceSnapshot:
        return entity_models.DeviceSnapshot(
            device_id=snapshot.device_id,
            name=snapshot.name,
            captured_at=snapshot.captured_at,
            version=snapshot.version,
            manufacturer=snapshot.manufacturer,
            model=snapshot.model,
            serial_number=snapshot.serial_number,
            product_id=snapshot.product_id,
            management_ip=snapshot.management_ip,
            base_mac=snapshot.base_mac,
            software_version=snapshot.software_version,
            uptime=snapshot.uptime,
            hardware_revision=snapshot.hardware_revision,
            platform=snapshot.platform,
            stack_members=snapshot.stack_members,
            interfaces=tuple(
                entity_models.InterfaceSnapshot(
                    device_id=interface.device_id,
                    name=interface.name,
                    captured_at=interface.captured_at,
                    version=interface.version,
                    admin_status=interface.admin_status,
                    oper_status=interface.oper_status,
                    description=interface.description,
                    mac_address=interface.mac_address,
                    speed_mbps=interface.speed_mbps,
                    poe_status=interface.poe_status,
                )
                for interface in snapshot.interfaces
            ),
            vlans=tuple(
                entity_models.VLANSnapshot(
                    vlan_id=vlan.vlan_id,
                    name=vlan.name,
                    captured_at=vlan.captured_at,
                    version=vlan.version,
                    device_id=vlan.device_id,
                    status=vlan.status,
                )
                for vlan in snapshot.vlans
            ),
            mac_table=tuple(
                entity_models.MACTableSnapshot(
                    mac_address=entry.mac_address,
                    device_id=entry.device_id,
                    interface_name=entry.interface_name,
                    captured_at=entry.captured_at,
                    version=entry.version,
                    vlan_id=entry.vlan_id,
                    last_seen=entry.last_seen,
                )
                for entry in snapshot.mac_table
            ),
            neighbors=tuple(
                entity_models.NeighborSnapshot(
                    local_device_id=neighbor.local_device_id,
                    local_interface=neighbor.local_interface,
                    remote_device_id=neighbor.remote_device_id,
                    remote_interface=neighbor.remote_interface,
                    protocol=neighbor.protocol,
                    captured_at=neighbor.captured_at,
                    version=neighbor.version,
                )
                for neighbor in snapshot.neighbors
            ),
            power=(
                entity_models.PowerSnapshot(
                    device_id=snapshot.power.device_id,
                    source=snapshot.power.source,
                    captured_at=snapshot.power.captured_at,
                    version=snapshot.power.version,
                    status=snapshot.power.status,
                    available_watts=snapshot.power.available_watts,
                    consumed_watts=snapshot.power.consumed_watts,
                    poe_enabled=snapshot.power.poe_enabled,
                )
                if snapshot.power is not None
                else None
            ),
        )
