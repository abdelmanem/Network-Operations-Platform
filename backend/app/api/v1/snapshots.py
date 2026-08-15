"""Snapshot detail API endpoints for drilling into inventory records."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.persistence.repositories import SnapshotRepository
from backend.app.schemas.inventory import DeviceSnapshotItem
from backend.app.schemas.snapshots import (
    InterfaceListResponse,
    InterfaceResponse,
    NeighborListResponse,
    NeighborResponse,
    SnapshotDeviceListResponse,
    SnapshotResponse,
    VlanListResponse,
    VlanResponse,
)

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get(
    "/{snapshot_id}",
    response_model=SnapshotResponse,
    summary="Get snapshot metadata",
)
def get_snapshot(
    db_session: Annotated[Session, Depends(get_db_session)],
    snapshot_id: UUID,
) -> SnapshotResponse:
    """Get metadata for a snapshot, including device/interface/VLAN/neighbor counts."""

    repo = SnapshotRepository(db_session)
    snapshot = repo.get(snapshot_id)

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found.",
        )

    devices = repo.get_snapshot_devices(snapshot_id)
    interfaces = repo.get_snapshot_interfaces(snapshot_id)
    vlans = repo.get_snapshot_vlans(snapshot_id)
    neighbors = repo.get_snapshot_neighbors(snapshot_id)

    return SnapshotResponse(
        id=snapshot.id,
        source=snapshot.source,
        device_count=len(devices),
        interface_count=len(interfaces),
        vlan_count=len(vlans),
        neighbor_count=len(neighbors),
        captured_at=snapshot.captured_at,
    )


@router.get(
    "/{snapshot_id}/devices",
    response_model=SnapshotDeviceListResponse,
    summary="List devices in snapshot",
)
def list_snapshot_devices(
    db_session: Annotated[Session, Depends(get_db_session)],
    snapshot_id: UUID,
) -> SnapshotDeviceListResponse:
    """List all devices in a snapshot."""

    repo = SnapshotRepository(db_session)
    snapshot = repo.get(snapshot_id)

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found.",
        )

    devices = repo.get_snapshot_devices(snapshot_id)

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
        ).model_dump()
        for d in devices
    ]

    return SnapshotDeviceListResponse(
        snapshot_id=snapshot_id,
        source=snapshot.source,
        device_count=len(devices),
        items=items,
    )


@router.get(
    "/{snapshot_id}/devices/{device_id}/interfaces",
    response_model=InterfaceListResponse,
    summary="List interfaces for device in snapshot",
)
def list_device_interfaces(
    db_session: Annotated[Session, Depends(get_db_session)],
    snapshot_id: UUID,
    device_id: str,
) -> InterfaceListResponse:
    """List all interfaces for a device in a snapshot."""

    repo = SnapshotRepository(db_session)
    snapshot = repo.get(snapshot_id)

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found.",
        )

    # Verify device exists in this snapshot
    devices = repo.get_snapshot_devices(snapshot_id, device_id=device_id)
    if not devices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found in snapshot.",
        )

    # Get interfaces for this device
    interfaces = repo.get_snapshot_interfaces(snapshot_id, device_id=device_id)

    items = [
        InterfaceResponse(
            name=i.name,
            admin_status=i.admin_status,
            oper_status=i.oper_status,
            description=i.description,
            mac_address=i.mac_address,
            speed_mbps=i.speed_mbps,
            poe_status=i.poe_status,
        )
        for i in interfaces
    ]

    return InterfaceListResponse(
        snapshot_id=snapshot_id,
        device_id=device_id,
        interface_count=len(interfaces),
        items=items,
    )


@router.get(
    "/{snapshot_id}/devices/{device_id}/vlans",
    response_model=VlanListResponse,
    summary="List VLANs for device in snapshot",
)
def list_device_vlans(
    db_session: Annotated[Session, Depends(get_db_session)],
    snapshot_id: UUID,
    device_id: str,
) -> VlanListResponse:
    """List all VLANs for a device in a snapshot."""

    repo = SnapshotRepository(db_session)
    snapshot = repo.get(snapshot_id)

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found.",
        )

    # Verify device exists in this snapshot
    devices = repo.get_snapshot_devices(snapshot_id, device_id=device_id)
    if not devices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found in snapshot.",
        )

    # Get VLANs for this device
    vlans = repo.get_snapshot_vlans(snapshot_id, device_id=device_id)

    items = [
        VlanResponse(
            vlan_id=v.vlan_id,
            name=v.name,
            status=v.status,
        )
        for v in vlans
    ]

    return VlanListResponse(
        snapshot_id=snapshot_id,
        device_id=device_id,
        vlan_count=len(vlans),
        items=items,
    )


@router.get(
    "/{snapshot_id}/devices/{device_id}/neighbors",
    response_model=NeighborListResponse,
    summary="List neighbors for device in snapshot",
)
def list_device_neighbors(
    db_session: Annotated[Session, Depends(get_db_session)],
    snapshot_id: UUID,
    device_id: str,
) -> NeighborListResponse:
    """List all discovered neighbors for a device in a snapshot."""

    repo = SnapshotRepository(db_session)
    snapshot = repo.get(snapshot_id)

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found.",
        )

    # Verify device exists in this snapshot
    devices = repo.get_snapshot_devices(snapshot_id, device_id=device_id)
    if not devices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device {device_id} not found in snapshot.",
        )

    # Get neighbors for this device
    neighbors = repo.get_snapshot_neighbors(snapshot_id, device_id=device_id)

    items = [
        NeighborResponse(
            neighbor_id=n.remote_device_id,
            remote_device_id=n.remote_device_id,
            remote_interface=n.remote_interface,
            local_interface=n.local_interface,
            protocol=n.protocol,
        )
        for n in neighbors
    ]

    return NeighborListResponse(
        snapshot_id=snapshot_id,
        device_id=device_id,
        neighbor_count=len(neighbors),
        items=items,
    )
