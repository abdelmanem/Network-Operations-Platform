"""Abstract transport primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from backend.app.transports.credentials import CredentialReference, TransportCredentials
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.session import TransportSession
from backend.app.transports.timeout import TransportTimeout


class TransportCapability(StrEnum):
    """Reusable transport capability identifiers."""

    SSH = "SSH"
    SNMP = "SNMP"
    TELNET = "TELNET"
    ICMP = "ICMP"
    HTTP = "HTTP"
    HTTPS = "HTTPS"


class TransportSecurity(StrEnum):
    """Security classification used by discovery policy."""

    SECURE = "secure"
    INSECURE = "insecure"


@dataclass(frozen=True, slots=True)
class TransportTarget:
    """Identify a target for transport initialization."""

    identifier: str
    address: str
    metadata: dict[str, object] = field(default_factory=dict)
    credential_reference: CredentialReference | None = None


@dataclass(slots=True)
class TransportContext:
    """Execution context shared with transports."""

    target: TransportTarget
    capabilities: frozenset[TransportCapability] = field(default_factory=frozenset)
    credentials: TransportCredentials | None = None
    timeout: TransportTimeout | None = None
    retry_policy: TransportRetryPolicy | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class BaseTransport(ABC):
    """Abstract transport interface."""

    name: str
    capabilities: frozenset[TransportCapability]
    security: TransportSecurity = TransportSecurity.SECURE

    @abstractmethod
    def health_check(self, context: TransportContext) -> None:
        """Validate transport readiness for the supplied context."""

    @abstractmethod
    def create_session(self, context: TransportContext) -> TransportSession:
        """Create a transport session."""

    @abstractmethod
    def close(self) -> None:
        """Release transport-level resources."""
