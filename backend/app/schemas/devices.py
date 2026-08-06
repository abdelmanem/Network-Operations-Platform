from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceHistoryItem(BaseModel):
    id: UUID
    device_id: str
    name: str
    model: str | None = None
    serial_number: str | None = None
    platform: str | None = None
    created_at: datetime


class DeviceHistoryResponse(BaseModel):
    device_id: str
    items: list[DeviceHistoryItem] = Field(default_factory=list)
