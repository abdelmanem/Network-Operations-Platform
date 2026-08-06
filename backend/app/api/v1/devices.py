from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.persistence.models import SnapshotSource
from backend.app.persistence.repositories import SnapshotRepository
from backend.app.schemas.devices import DeviceHistoryItem, DeviceHistoryResponse

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get(
    "/{device_id}/history",
    response_model=DeviceHistoryResponse,
    summary="Get device history",
)
def get_device_history(
    device_id: str,
    db_session: Annotated[Session, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> DeviceHistoryResponse:
    repository = SnapshotRepository(db_session)
    snapshots = repository.list_by_source(SnapshotSource.LIVE)
    items: list[dict[str, object]] = []
    for snapshot in snapshots:
        for device in getattr(snapshot, "devices", []):
            if device.device_id == device_id:
                items.append(
                    {
                        "id": device.id,
                        "device_id": device.device_id,
                        "name": device.name,
                        "model": device.model,
                        "serial_number": device.serial_number,
                        "platform": device.platform,
                        "created_at": device.created_at,
                    }
                )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device history not found",
        )
    start = (page - 1) * page_size
    end = start + page_size
    return DeviceHistoryResponse(
        device_id=device_id,
        items=[
            DeviceHistoryItem(
                id=UUID(str(item["id"])),
                device_id=str(item["device_id"]),
                name=str(item["name"]),
                model=str(item["model"]) if item["model"] is not None else None,
                serial_number=(
                    str(item["serial_number"])
                    if item["serial_number"] is not None
                    else None
                ),
                platform=(
                    str(item["platform"]) if item["platform"] is not None else None
                ),
                created_at=cast(datetime, item["created_at"]),
            )
            for item in items[start:end]
        ],
    )
