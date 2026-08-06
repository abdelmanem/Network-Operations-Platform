from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.app.schemas.common import PaginatedResponse
from pydantic import BaseModel, Field


class EvidenceResponse(BaseModel):
    id: UUID
    source: str
    description: str
    reference: str | None = None
    details: dict[str, object] = Field(default_factory=dict)
    captured_at: datetime


class FindingResponse(BaseModel):
    id: UUID
    finding_id: UUID
    rule_id: str
    title: str
    severity: str
    description: str
    expected_state: dict[str, object] = Field(default_factory=dict)
    observed_state: dict[str, object] = Field(default_factory=dict)
    evidence: list[EvidenceResponse] = Field(default_factory=list)
    created_at: datetime


class FindingsListResponse(PaginatedResponse[FindingResponse]):
    """Paginated findings."""

    pass
