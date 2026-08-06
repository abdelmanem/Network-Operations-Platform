from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ComplianceSummaryResponse(BaseModel):
    id: UUID
    expected_snapshot_id: UUID
    observed_snapshot_id: UUID
    compared_at: datetime
    metrics: dict[str, object] = Field(default_factory=dict)
    findings: list[dict[str, object]] = Field(default_factory=list)
