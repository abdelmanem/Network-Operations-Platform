"""Inventory API endpoints for listing NetBox expected and live discovered inventory."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.persistence.models import SnapshotDeviceRecord, SnapshotRecord
from backend.app.persistence.repositories import SnapshotRepository
from backend.app.schemas.inventory import DeviceSnapshotItem, InventoryListResponse

router = APIRouter(prefix="/inventory", tags=["inventory"])

InventorySortField = Literal[
    "name", "model", "serial_number", "platform", "management_ip"
]
SortDirection = Literal["asc", "desc"]


def _inventory_response(
    snapshot: SnapshotRecord,
    devices: Sequence[SnapshotDeviceRecord],
    *,
    page: int,
    page_size: int,
    search: str | None,
    manufacturer: str | None,
    platform: str | None,
    sort_by: InventorySortField,
    sort_direction: SortDirection,
) -> InventoryListResponse:
    """Filter and sort a complete snapshot before applying pagination."""

    normalized_search = search.strip().casefold() if search else ""
    normalized_manufacturer = manufacturer.strip().casefold() if manufacturer else ""
    normalized_platform = platform.strip().casefold() if platform else ""
    manufacturers = sorted(
        {device.manufacturer for device in devices if device.manufacturer}
    )
    platforms = sorted({device.platform for device in devices if device.platform})

    def matches(device: SnapshotDeviceRecord) -> bool:
        values = (
            device.device_id,
            device.name,
            device.manufacturer,
            device.model,
            device.serial_number,
            device.product_id,
            device.management_ip,
            device.platform,
        )
        return (
            (
                not normalized_search
                or any(
                    normalized_search in (value or "").casefold() for value in values
                )
            )
            and (
                not normalized_manufacturer
                or (device.manufacturer or "").casefold() == normalized_manufacturer
            )
            and (
                not normalized_platform
                or (device.platform or "").casefold() == normalized_platform
            )
        )

    filtered_devices = [device for device in devices if matches(device)]
    filtered_devices.sort(
        key=lambda device: (getattr(device, sort_by) or "").casefold(),
        reverse=sort_direction == "desc",
    )
    start = (page - 1) * page_size
    end = start + page_size

    return InventoryListResponse(
        source=snapshot.source,
        snapshot_id=snapshot.id,
        snapshot_captured_at=snapshot.captured_at,
        device_count=len(devices),
        items=[
            DeviceSnapshotItem(
                device_id=device.device_id,
                name=device.name,
                manufacturer=device.manufacturer,
                model=device.model,
                serial_number=device.serial_number,
                product_id=device.product_id,
                management_ip=device.management_ip,
                platform=device.platform,
            )
            for device in filtered_devices[start:end]
        ],
        page=page,
        page_size=page_size,
        total=len(filtered_devices),
        has_next=end < len(filtered_devices),
        manufacturers=manufacturers,
        platforms=platforms,
    )


@router.get(
    "/netbox",
    response_model=InventoryListResponse,
    summary="List NetBox expected inventory",
)
def list_netbox_inventory(
    db_session: Annotated[Session, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=200),
    manufacturer: str | None = Query(default=None, max_length=255),
    platform: str | None = Query(default=None, max_length=255),
    sort_by: InventorySortField = "name",
    sort_direction: SortDirection = "asc",
) -> InventoryListResponse:
    """
    List all devices from the latest NetBox snapshot (expected state).

    This endpoint returns the canonical expected network inventory from NetBox,
    which serves as the baseline for network operations.
    """

    repo = SnapshotRepository(db_session)
    snapshot = repo.get_latest("netbox")

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No NetBox snapshot found. Run discovery first.",
        )

    # Get all devices in this snapshot
    all_devices = repo.get_snapshot_devices(snapshot.id)

    return _inventory_response(
        snapshot,
        all_devices,
        page=page,
        page_size=page_size,
        search=search,
        manufacturer=manufacturer,
        platform=platform,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )


@router.get(
    "/live",
    response_model=InventoryListResponse,
    summary="List live discovered inventory",
)
def list_live_inventory(
    db_session: Annotated[Session, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=200),
    manufacturer: str | None = Query(default=None, max_length=255),
    platform: str | None = Query(default=None, max_length=255),
    sort_by: InventorySortField = "name",
    sort_direction: SortDirection = "asc",
) -> InventoryListResponse:
    """
    List all devices from the latest live discovery snapshot (observed state).

    This endpoint returns the actual devices discovered in the real network,
    which can be compared against NetBox to identify drift.
    """

    repo = SnapshotRepository(db_session)
    snapshot = repo.get_latest("live")

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live snapshot found. Run discovery first.",
        )

    # Get all devices in this snapshot
    all_devices = repo.get_snapshot_devices(snapshot.id)

    return _inventory_response(
        snapshot,
        all_devices,
        page=page,
        page_size=page_size,
        search=search,
        manufacturer=manufacturer,
        platform=platform,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
