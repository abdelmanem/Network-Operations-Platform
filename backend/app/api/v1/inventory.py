"""Inventory API endpoints for listing NetBox expected and live discovered inventory."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.persistence.repositories import SnapshotRepository
from backend.app.schemas.inventory import DeviceSnapshotItem, InventoryListResponse

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get(
    "/netbox",
    response_model=InventoryListResponse,
    summary="List NetBox expected inventory",
)
def list_netbox_inventory(
    db_session: Annotated[Session, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
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

    # Apply pagination
    start = (page - 1) * page_size
    end = start + page_size
    paginated_devices = all_devices[start:end]

    items = [
        DeviceSnapshotItem(
            device_id=d.device_id,
            name=d.name,
            manufacturer=d.manufacturer,
            model=d.model,
            serial_number=d.serial_number,
            product_id=d.product_id,
            management_ip=d.management_ip,
            platform=d.platform,
        )
        for d in paginated_devices
    ]

    return InventoryListResponse(
        source="netbox",
        snapshot_id=snapshot.id,
        snapshot_captured_at=snapshot.captured_at,
        device_count=len(all_devices),
        items=items,
        page=page,
        page_size=page_size,
        total=len(all_devices),
        has_next=end < len(all_devices),
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

    # Apply pagination
    start = (page - 1) * page_size
    end = start + page_size
    paginated_devices = all_devices[start:end]

    items = [
        DeviceSnapshotItem(
            device_id=d.device_id,
            name=d.name,
            manufacturer=d.manufacturer,
            model=d.model,
            serial_number=d.serial_number,
            product_id=d.product_id,
            management_ip=d.management_ip,
            platform=d.platform,
        )
        for d in paginated_devices
    ]

    return InventoryListResponse(
        source="live",
        snapshot_id=snapshot.id,
        snapshot_captured_at=snapshot.captured_at,
        device_count=len(all_devices),
        items=items,
        page=page,
        page_size=page_size,
        total=len(all_devices),
        has_next=end < len(all_devices),
    )
