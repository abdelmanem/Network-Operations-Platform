"""Inventory section builder."""

from __future__ import annotations

from types import MappingProxyType

from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import SectionType
from backend.app.reporting.models import ReportSection
from backend.app.reporting.statistics import ReportStatistics


def build_inventory_section(
    context: ReportContext,
    statistics: ReportStatistics,
) -> ReportSection:
    """Build structured inventory section data."""

    netbox_devices: tuple[dict[str, object], ...] = ()
    live_devices: tuple[dict[str, object], ...] = ()

    if context.netbox_inventory is not None:
        netbox_devices = tuple(
            {
                "name": device.name,
                "serial": device.serial,
                "platform": device.platform.name if device.platform else None,
                "device_type": device.device_type.model,
                "manufacturer": device.device_type.manufacturer.name,
            }
            for device in context.netbox_inventory.devices
        )

    if context.live_snapshot is not None:
        live_devices = tuple(
            {
                "device_id": device.device_id,
                "name": device.name,
                "serial_number": device.serial_number,
                "platform": device.platform,
                "model": device.model,
                "manufacturer": device.manufacturer,
                "management_ip": device.management_ip,
            }
            for device in context.live_snapshot.devices
        )

    return ReportSection(
        section_type=SectionType.INVENTORY,
        title="section.inventory",
        data=MappingProxyType(
            {
                "netbox_devices": netbox_devices,
                "live_devices": live_devices,
                "device_type_counts": statistics.device_type_counts,
                "vendor_counts": statistics.vendor_counts,
                "platform_counts": statistics.platform_counts,
            }
        ),
    )
