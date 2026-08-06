from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.app.schemas.common import PaginatedResponse
from pydantic import BaseModel


class DeviceHistoryEntry(BaseModel):
    id: UUID
    device_id: str
    name: str
    model: str | None = None
    serial_number: str | None = None
    platform: str | None = None
    created_at: datetime


class DeviceHistoryResponse(PaginatedResponse[DeviceHistoryEntry]):
    """Paginated device history."""

    pass
