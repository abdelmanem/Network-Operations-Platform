"""Schemas for inventory API responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.app.schemas.common import PaginatedResponse
from pydantic import BaseModel, Field


class DeviceSnapshotItem(BaseModel):
    """Single device from a snapshot."""

    device_id: str
    name: str
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    product_id: str | None = None
    management_ip: str | None = None
    platform: str | None = None


class InventoryListResponse(PaginatedResponse[DeviceSnapshotItem]):
    """Paginated list of devices from an inventory snapshot."""

    source: str = Field(description="Source of inventory: 'netbox' or 'live'")
    snapshot_id: UUID | None = Field(
        description="ID of the snapshot this inventory came from"
    )
    snapshot_captured_at: datetime | None = Field(
        description="When the snapshot was captured"
    )
    device_count: int = Field(description="Total number of devices in snapshot")
    manufacturers: list[str] = Field(
        default_factory=list,
        description="Available manufacturer filters for the complete snapshot",
    )
    platforms: list[str] = Field(
        default_factory=list,
        description="Available platform filters for the complete snapshot",
    )
