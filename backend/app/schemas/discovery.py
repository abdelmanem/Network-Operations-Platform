from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from backend.app.discovery.contracts import (
    DiscoveryFailureCode,
    DiscoveryJobStatus,
    DiscoveryScopeType,
    validate_scope,
)
from backend.app.schemas.common import PaginatedResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DiscoveryTargetRequest(BaseModel):
    """Validated tenant-owned target contract for M31 discovery."""

    model_config = ConfigDict(extra="forbid")

    identifier: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=512)
    scope_type: DiscoveryScopeType = DiscoveryScopeType.SINGLE_DEVICE
    scope_end: str | None = Field(default=None, max_length=512)
    scope_cidr: str | None = Field(default=None, max_length=512)
    hostname: str | None = Field(default=None, max_length=255)
    vendor: str | None = Field(default=None, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=255)
    platform_hint: str | None = Field(default=None, max_length=128)
    preferred_transport: str | None = Field(default=None, max_length=64)
    enabled: bool = True
    credential_reference: str | None = Field(default=None, max_length=255)
    credential_profile_id: str | None = Field(default=None, max_length=255)
    credential_references: dict[str, str] = Field(default_factory=dict)
    allowed_fallback_transports: list[str] = Field(default_factory=list)
    allow_insecure_telnet: bool = False
    allow_insecure_http: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("identifier", "tenant_id")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        """Reject whitespace-only contract values."""

        if not value.strip():
            raise ValueError("Value cannot be blank.")
        return value

    @model_validator(mode="after")
    def validate_scope_definition(self) -> DiscoveryTargetRequest:
        validate_scope(
            self.scope_type,
            address=self.address,
            scope_end=self.scope_end,
            scope_cidr=self.scope_cidr,
        )
        if self.credential_profile_id is None and self.credential_reference is None:
            raise ValueError("A credential profile is required.")

        uses_telnet = (
            (self.preferred_transport and self.preferred_transport.lower() == "telnet")
            or "telnet" in {t.lower() for t in self.allowed_fallback_transports}
        )
        if uses_telnet and not self.allow_insecure_telnet:
            raise ValueError(
                "Telnet is insecure. Set allow_insecure_telnet=true to explicitly enable."
            )
        uses_http = (
            (self.preferred_transport and self.preferred_transport.lower() == "http")
            or "http" in {t.lower() for t in self.allowed_fallback_transports}
        )
        if uses_http and not self.allow_insecure_http:
            raise ValueError(
                "HTTP is insecure. Set allow_insecure_http=true to explicitly enable."
            )
        return self

    @field_validator("platform_hint")
    @classmethod
    def validate_platform_hint(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        supported = {
            "cisco-ios",
            "cisco-iosxe",
            "ios",
            "iosxe",
            "cisco-ios-xe",
            "cisco-ios-x",
        }
        if normalized not in supported:
            raise ValueError("Unsupported discovery platform.")
        return value

    @field_validator("preferred_transport")
    @classmethod
    def validate_transport(cls, value: str | None) -> str | None:
        supported = {
            "ssh",
            "snmp",
            "telnet",
            "icmp",
            "http",
            "https",
            "cisco-api",
            "netmiko",
            "paramiko",
            "pysnmp",
            "httpx",
        }
        if value is not None and value not in supported:
            raise ValueError("Unsupported discovery transport.")
        return value

    @field_validator("allowed_fallback_transports")
    @classmethod
    def validate_fallback_transports(cls, value: list[str]) -> list[str]:
        supported = {"ssh", "snmp", "telnet", "icmp", "http", "https", "cisco-api"}
        if any(transport not in supported for transport in value):
            raise ValueError("Unsupported discovery fallback transport.")
        return list(dict.fromkeys(value))


class DiscoveryTargetUpdateRequest(BaseModel):
    """Validated target update contract."""

    model_config = ConfigDict(extra="forbid")

    credential_profile_id: str | None = Field(default=None, max_length=255)
    preferred_transport: str | None = Field(default=None, max_length=64)
    platform_hint: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None

    @field_validator("platform_hint")
    @classmethod
    def validate_platform_hint(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        supported = {
            "cisco-ios",
            "cisco-iosxe",
            "ios",
            "iosxe",
            "cisco-ios-xe",
            "cisco-ios-x",
        }
        if normalized not in supported:
            raise ValueError("Unsupported discovery platform.")
        return value

    @field_validator("preferred_transport")
    @classmethod
    def validate_transport(cls, value: str | None) -> str | None:
        supported = {
            "ssh",
            "snmp",
            "telnet",
            "icmp",
            "http",
            "https",
            "cisco-api",
            "netmiko",
            "paramiko",
            "pysnmp",
            "httpx",
        }
        if value is not None and value not in supported:
            raise ValueError("Unsupported discovery transport.")
        return value


class DiscoveryTargetResponse(BaseModel):
    """Persisted target metadata returned to the operator UI."""

    target_id: UUID
    tenant_id: str
    identifier: str
    address: str
    scope_type: DiscoveryScopeType
    scope_end: str | None = None
    scope_cidr: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    platform_hint: str | None = None
    preferred_transport: str | None = None
    allowed_fallback_transports: list[str] = Field(default_factory=list)
    allow_insecure_telnet: bool = False
    allow_insecure_http: bool = False
    credential_references: list[str] = Field(default_factory=list)
    credential_profile_id: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CredentialProfileRequest(BaseModel):
    """Create a tenant-scoped credential profile reference."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    vendor: str | None = Field(default=None, max_length=128)
    platform: str | None = Field(default=None, max_length=128)
    credential_type: str | None = Field(default=None, max_length=64)
    username: str | None = Field(default=None, max_length=255)
    transport_types: list[str] = Field(default_factory=list)
    provider_reference: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value

    @field_validator("transport_types")
    @classmethod
    def validate_transport_types(cls, value: list[str]) -> list[str]:
        supported = {
            "ssh",
            "snmp",
            "snmpv2c",
            "snmpv3",
            "telnet",
            "https",
            "http",
            "icmp",
        }
        cleaned = [str(item).strip().lower() for item in value]
        if not cleaned:
            raise ValueError("At least one transport type is required.")
        if any(item not in supported for item in cleaned):
            raise ValueError("Unsupported transport type.")
        return list(dict.fromkeys(cleaned))


class CredentialProfileUpdateRequest(BaseModel):
    """Update a tenant-scoped credential profile without exposing secret material."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    vendor: str | None = Field(default=None, max_length=128)
    platform: str | None = Field(default=None, max_length=128)
    credential_type: str | None = Field(default=None, max_length=64)
    username: str | None = Field(default=None, max_length=255)
    transport_types: list[str] | None = Field(default=None)
    enabled: bool | None = None


class CredentialProfileResponse(BaseModel):
    """Secret-free credential profile metadata returned to the UI."""

    profile_id: UUID
    tenant_id: str
    name: str
    description: str | None = None
    vendor: str | None = None
    platform: str | None = None
    credential_type: str | None = None
    username: str | None = None
    transport_types: list[str] = Field(default_factory=list)
    provider_reference: str
    secret_status: str = "configured"
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CredentialProfileTestRequest(BaseModel):
    """Validate a credential profile against a target transport at runtime."""

    model_config = ConfigDict(extra="forbid")

    transport: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=512)

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, value: str) -> str:
        cleaned = value.strip().lower()
        supported = {"ssh", "snmp", "telnet", "http", "https", "icmp"}
        if cleaned not in supported:
            raise ValueError("Unsupported transport for credential validation.")
        return cleaned


class CredentialProfileTestResponse(BaseModel):
    """Sanitized execution-time credential validation result."""

    status: str
    transport: str
    target: str
    credential_type: str | None = None
    message: str
    provider_reference: str | None = None


class DiscoveryJobRequest(BaseModel):
    """Request to execute discovery for an existing target."""

    model_config = ConfigDict(extra="forbid")

    target_id: UUID
    requested_capabilities: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
    timeout_seconds: float | None = Field(default=None, ge=0.0)
    correlation_id: str | None = Field(default=None, max_length=255)

    @field_validator("requested_capabilities")
    @classmethod
    def validate_requested_collector(
        cls, value: dict[str, object]
    ) -> dict[str, object]:
        collector_name = value.get("collector_name")
        if collector_name is not None and collector_name != "cisco-ios-inventory":
            raise ValueError("Unsupported discovery collector.")
        return value


class DiscoveryJobCancellationRequest(BaseModel):
    """Operator request for cooperative cancellation of a discovery job."""

    reason: str = Field(default="Cancelled by operator", min_length=1, max_length=1024)


class DiscoveryJobResponse(BaseModel):
    """Durable discovery job status contract."""

    job_id: UUID
    tenant_id: str
    target_id: UUID
    target_identifier: str | None = None
    target_address: str | None = None
    discovery_run_id: UUID | None = None
    status: DiscoveryJobStatus
    selected_transport: str | None = None
    selected_platform: str | None = None
    attempts: int = Field(ge=0)
    error_code: DiscoveryFailureCode | str | None = None
    error_message: str | None = None
    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    timeout_seconds: float | None = Field(default=None, ge=0.0)
    correlation_id: str | None = None
    cancellation_requested_at: datetime | None = None
    cancellation_requested_by: UUID | None = None
    cancellation_reason: str | None = None
    execution_owner: UUID | None = None
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    has_active_lease: bool = False


class DiscoveryJobListResponse(PaginatedResponse[DiscoveryJobResponse]):
    """Tenant-scoped page of durable discovery jobs."""

    total_pages: int = 1


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


class DiscoveryDeviceResultResponse(BaseModel):
    """Per-device result shown for a scoped discovery job."""

    result_id: UUID
    address: str
    hostname: str | None = None
    vendor: str | None = None
    model: str | None = None
    platform: str | None = None
    state: str
    result_state: str | None = None
    selected_transport: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    correlation_id: str | None = None


class DiscoveryTransportAttemptResponse(BaseModel):
    """Secret-free transport attempt history."""

    attempt_id: UUID
    transport: str
    attempt_order: int
    result: str
    failure_code: str | None = None
    duration_ms: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
    correlation_id: str | None = None


class DiscoveryRunSummary(BaseModel):
    """Summary of a persisted discovery run with detailed result categories."""

    id: UUID
    target_identifier: str
    target_address: str | None = None
    status: str
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Summary counts by result state
    total_scanned: int | None = Field(default=None, ge=0)
    total_discovered: int | None = Field(default=None, ge=0)
    total_unreachable: int | None = Field(default=None, ge=0)
    total_reachable_no_management: int | None = Field(default=None, ge=0)
    total_authentication_failed: int | None = Field(default=None, ge=0)
    total_partial_discovery: int | None = Field(default=None, ge=0)


class DiscoveryRunListResponse(PaginatedResponse[DiscoveryRunSummary]):
    """Paginated discovery run history."""

    pass
