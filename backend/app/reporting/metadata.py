"""Report metadata models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from uuid import UUID

from backend.app.reporting.enums import ReportType


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    """Immutable report metadata."""

    title: str
    report_type: ReportType
    run_id: UUID | None = None
    job_id: UUID | None = None
    generated_at: datetime | None = None
    site: str | None = None
    device_role: str | None = None
    platform: str | None = None
    source: str | None = None
    attributes: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
