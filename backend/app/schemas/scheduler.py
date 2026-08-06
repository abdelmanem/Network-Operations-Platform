from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)

    name: str = Field(min_length=1)
    kind: str = Field(default="discovery")
    schedule_type: str = Field(default="interval")
    enabled: bool = True
    interval_seconds: int | None = None
    start_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)

    name: str | None = None
    enabled: bool | None = None


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    kind: str
    schedule_type: str
    enabled: bool
    interval_seconds: int | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    state: str
