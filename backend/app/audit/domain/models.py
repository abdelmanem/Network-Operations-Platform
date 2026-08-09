"""Immutable audit domain records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        marker in lowered
        for marker in (
            "password",
            "secret",
            "token",
            "authorization",
            "jwt",
            "credential",
            "cookie",
            "private_key",
        )
    )


def _sanitize_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(k): _sanitize_value(v)
            for k, v in value.items()
            if not _is_sensitive_key(str(k))
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Immutable security and governance audit record."""

    id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor_id: UUID | None = None
    tenant_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    outcome: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    category: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        actor_id: UUID | None = None,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        outcome: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        source: str | None = None,
        category: str | None = None,
        timestamp: datetime | None = None,
    ) -> AuditRecord:
        sanitized_metadata = {
            str(key): _sanitize_value(value)
            for key, value in (metadata or {}).items()
            if not _is_sensitive_key(str(key))
        }
        now = timestamp or datetime.now(UTC)
        return cls(
            event_type=event_type,
            timestamp=now,
            actor_id=actor_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
            metadata=sanitized_metadata,
            source=source,
            category=category,
            created_at=now,
        )
