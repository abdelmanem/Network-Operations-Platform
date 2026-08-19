from __future__ import annotations

from datetime import datetime
from uuid import UUID

from backend.app.discovery.contracts import DiscoveryFailureCode, DiscoveryJobStatus
from backend.app.schemas.common import PaginatedResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiscoveryTargetRequest(BaseModel):
    """Validated tenant-owned target contract for M31 discovery."""

    model_config = ConfigDict(extra="forbid")

    identifier: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=512)
    tenant_id: str = Field(min_length=1, max_length=255)
    platform_hint: str | None = Field(default=None, max_length=128)
    preferred_transport: str | None = Field(default=None, max_length=64)
    enabled: bool = True
    credential_reference: str = Field(min_length=1, max_length=255)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("identifier", "address", "tenant_id", "credential_reference")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        """Reject whitespace-only contract values."""

        if not value.strip():
            raise ValueError("Value cannot be blank.")
        return value


class DiscoveryJobResponse(BaseModel):
    """Durable discovery job status contract."""

    job_id: UUID
    tenant_id: str
    target_id: UUID
    discovery_run_id: UUID | None = None
    status: DiscoveryJobStatus
    selected_transport: str | None = None
    selected_platform: str | None = None
    attempts: int = Field(ge=0)
    error_code: DiscoveryFailureCode | None = None
    error_message: str | None = None
    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    timeout_seconds: float | None = Field(default=None, ge=0.0)
    correlation_id: str | None = None


class DiscoveryEvidenceResponse(BaseModel):
    """Traceable discovery evidence metadata contract."""

    evidence_id: UUID
    tenant_id: str
    target_id: UUID
    discovery_job_id: UUID
    discovery_run_id: UUID
    collector_name: str
    platform: str
    transport: str
    evidence_type: str
    command_or_probe: str
    payload: dict[str, object]
    captured_at: datetime
    sequence: int = Field(ge=0)
    parser_version: str | None = None
    normalization_version: str | None = None
    content_hash: str


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
