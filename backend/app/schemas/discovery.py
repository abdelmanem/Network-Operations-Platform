from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.app.schemas.common import PaginatedResponse
from pydantic import BaseModel, Field


class DiscoveryRunSummary(BaseModel):
    """Summary of a persisted discovery run."""

    id: UUID
    target_identifier: str
    target_address: str | None = None
    status: str
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DiscoveryRunListResponse(PaginatedResponse[DiscoveryRunSummary]):
    """Paginated discovery run history."""

    pass
