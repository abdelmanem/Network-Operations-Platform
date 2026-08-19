"""M31 discovery domain contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from ipaddress import ip_address, ip_network
from typing import Any
from uuid import UUID, uuid4

from backend.app.transports.base import TransportCapability


class DiscoveryJobStatus(StrEnum):
    """Durable discovery job lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Return whether the job can no longer transition."""

        return self in {
            self.SUCCEEDED,
            self.FAILED,
            self.TIMED_OUT,
            self.CANCELLED,
        }


class DiscoveryFailureCode(StrEnum):
    """Stable failure codes exposed by discovery execution."""

    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    TARGET_DISABLED = "TARGET_DISABLED"
    UNSUPPORTED_VENDOR = "UNSUPPORTED_VENDOR"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    CONNECTION_TIMEOUT = "CONNECTION_TIMEOUT"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    TIMEOUT = "TIMEOUT"
    DISCOVERY_TIMEOUT = "DISCOVERY_TIMEOUT"
    DISCOVERY_FAILED = "DISCOVERY_FAILED"
    TRANSPORT_UNAVAILABLE = "TRANSPORT_UNAVAILABLE"
    UNSUPPORTED_PLATFORM = "UNSUPPORTED_PLATFORM"
    AMBIGUOUS_PLATFORM = "AMBIGUOUS_PLATFORM"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    COLLECTOR_FAILED = "COLLECTOR_FAILED"
    PARSER_FAILED = "PARSER_FAILED"
    NORMALIZATION_FAILED = "NORMALIZATION_FAILED"
    EVIDENCE_PERSISTENCE_FAILED = "EVIDENCE_PERSISTENCE_FAILED"
    SNAPSHOT_PERSISTENCE_FAILED = "SNAPSHOT_PERSISTENCE_FAILED"
    CANCELLED = "CANCELLED"


class DiscoveryScopeType(StrEnum):
    """Supported discovery scope boundaries."""

    SINGLE_DEVICE = "single_device"
    IP_RANGE = "ip_range"
    CIDR_NETWORK = "cidr_network"
    DEVICE_GROUP = "device_group"
    NETBOX_SCOPE = "netbox_scope"


def validate_scope(
    scope_type: DiscoveryScopeType,
    *,
    address: str | None = None,
    scope_end: str | None = None,
    scope_cidr: str | None = None,
) -> None:
    """Validate MVP single-device, range, and CIDR scope data."""

    if scope_type == DiscoveryScopeType.SINGLE_DEVICE:
        if not address:
            raise ValueError("A single-device scope requires an address.")
        ip_address(address)
    elif scope_type == DiscoveryScopeType.IP_RANGE:
        if not address or not scope_end:
            raise ValueError("An IP range requires start and end addresses.")
        start = ip_address(address)
        end = ip_address(scope_end)
        if start.version != end.version or int(start) > int(end):
            raise ValueError("IP range boundaries are invalid.")
    elif scope_type == DiscoveryScopeType.CIDR_NETWORK:
        if not scope_cidr:
            raise ValueError("A CIDR scope requires a network.")
        ip_network(scope_cidr, strict=False)
    elif scope_type in {
        DiscoveryScopeType.DEVICE_GROUP,
        DiscoveryScopeType.NETBOX_SCOPE,
    }:
        raise ValueError("This discovery scope is reserved for a future phase.")


@dataclass(frozen=True, slots=True)
class DiscoveryTransportPolicy:
    """Explicit ordered transport policy for one discovery target."""

    preferred: TransportCapability | None = None
    fallbacks: tuple[TransportCapability, ...] = ()
    allow_insecure_telnet: bool = False

    def ordered(self) -> tuple[TransportCapability, ...]:
        """Return the configured order without duplicates or implicit protocols."""

        configured = (
            () if self.preferred is None else (self.preferred,)
        ) + self.fallbacks
        if not self.allow_insecure_telnet and TransportCapability.TELNET in configured:
            raise ValueError("Telnet requires explicit insecure-transport approval.")
        return tuple(dict.fromkeys(configured))


_ALLOWED_TRANSITIONS: dict[DiscoveryJobStatus, frozenset[DiscoveryJobStatus]] = {
    DiscoveryJobStatus.QUEUED: frozenset(
        {DiscoveryJobStatus.RUNNING, DiscoveryJobStatus.CANCELLED}
    ),
    DiscoveryJobStatus.RUNNING: frozenset(
        {
            DiscoveryJobStatus.SUCCEEDED,
            DiscoveryJobStatus.FAILED,
            DiscoveryJobStatus.TIMED_OUT,
            DiscoveryJobStatus.CANCELLED,
        }
    ),
    DiscoveryJobStatus.SUCCEEDED: frozenset(),
    DiscoveryJobStatus.FAILED: frozenset(),
    DiscoveryJobStatus.TIMED_OUT: frozenset(),
    DiscoveryJobStatus.CANCELLED: frozenset(),
}


def transition_job(
    current: DiscoveryJobStatus,
    target: DiscoveryJobStatus,
) -> DiscoveryJobStatus:
    """Validate and return a legal discovery job transition."""

    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid discovery job transition: {current} -> {target}.")
    return target


@dataclass(frozen=True, slots=True)
class DiscoveryTraceability:
    """Identifiers that connect a discovery artifact to its execution."""

    tenant_id: str
    target_id: UUID
    job_id: UUID
    discovery_run_id: UUID

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("Tenant ID is required for discovery traceability.")


@dataclass(frozen=True, slots=True)
class DiscoveryEvidence:
    """Immutable, hashable evidence captured by a discovery collector."""

    traceability: DiscoveryTraceability
    collector_name: str
    platform: str
    transport: str
    evidence_type: str
    command_or_probe: str
    payload: dict[str, Any]
    captured_at: datetime
    sequence: int
    parser_version: str | None = None
    normalization_version: str | None = None
    id: UUID = field(default_factory=uuid4)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("Evidence sequence cannot be negative.")
        if not self.collector_name.strip() or not self.evidence_type.strip():
            raise ValueError("Evidence collector and type are required.")
        if self.captured_at.tzinfo is None:
            raise ValueError("Evidence timestamp must be timezone-aware.")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", self.compute_hash())

    def canonical_payload(self) -> str:
        """Return the deterministic representation used for hashing."""

        return json.dumps(self.payload, sort_keys=True, separators=(",", ":"))

    def compute_hash(self) -> str:
        """Return the SHA-256 hash of the evidence payload."""

        return hashlib.sha256(self.canonical_payload().encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Return whether the stored hash matches the payload."""

        return self.content_hash == self.compute_hash()


def new_traceability(
    *, tenant_id: str, target_id: UUID, job_id: UUID, discovery_run_id: UUID
) -> DiscoveryTraceability:
    """Construct a traceability value with explicit identifiers."""

    return DiscoveryTraceability(
        tenant_id=tenant_id,
        target_id=target_id,
        job_id=job_id,
        discovery_run_id=discovery_run_id,
    )


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for discovery contracts."""

    return datetime.now(UTC)


__all__ = [
    "DiscoveryEvidence",
    "DiscoveryFailureCode",
    "DiscoveryJobStatus",
    "DiscoveryTraceability",
    "new_traceability",
    "transition_job",
    "utc_now",
]
