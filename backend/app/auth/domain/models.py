from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class Permission:
    """Represents a single permission that can be granted to a role."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class Role:
    """Represents a role that groups permissions."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    permissions: tuple[Permission, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class User:
    """Represents a platform user."""

    id: UUID = field(default_factory=uuid4)
    username: str = ""
    email: str = ""
    password_hash: str = ""
    is_active: bool = True
    roles: tuple[Role, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class TokenPair:
    """Represents an issued access/refresh pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105


@dataclass(slots=True)
class AuditEvent:
    """Immutable security audit event."""

    id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    subject_id: UUID | None = None
    actor_id: UUID | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
