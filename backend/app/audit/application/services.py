"""Application service for audit logging."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any
from uuid import UUID

from backend.app.audit.domain.models import AuditRecord
from backend.app.events.bus import EventBus
from backend.app.events.models import BaseEvent


class AuditRepository(ABC):
    """Persistence port for immutable audit records."""

    @abstractmethod
    def create(
        self,
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
    ) -> AuditRecord: ...

    @abstractmethod
    def list(self, *, limit: int = 50) -> list[AuditRecord]: ...


class AuditService:
    """Application boundary for recording immutable audit activity."""

    def __init__(
        self,
        *,
        repository: AuditRepository | None = None,
        repository_factory: Callable[[], AuditRepository] | None = None,
    ) -> None:
        self._repository = repository
        self._repository_factory = repository_factory

    def _repository_instance(self) -> AuditRepository | None:
        if self._repository is not None:
            return self._repository
        if self._repository_factory is None:
            return None
        return self._repository_factory()

    def record(
        self,
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
    ) -> AuditRecord:
        record = AuditRecord.create(
            event_type=event_type,
            actor_id=actor_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
            metadata=metadata,
            source=source,
            category=category,
        )
        repository = self._repository_instance()
        if repository is None:
            return record
        return repository.create(
            event_type=record.event_type,
            actor_id=record.actor_id,
            tenant_id=record.tenant_id,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            outcome=record.outcome,
            request_id=record.request_id,
            metadata=record.metadata,
            source=record.source,
            category=record.category,
        )

    def record_security_event(
        self,
        *,
        event_type: str,
        actor_id: UUID | None = None,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        outcome: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        return self.record(
            event_type=event_type,
            actor_id=actor_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
            metadata=metadata,
            source="security",
            category="security",
        )

    def record_api_activity(
        self,
        *,
        event_type: str = "api.activity",
        actor_id: UUID | None = None,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        outcome: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        return self.record(
            event_type=event_type,
            actor_id=actor_id,
            tenant_id=tenant_id,
            resource_type=resource_type or "api",
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
            metadata=metadata,
            source="api",
            category="activity",
        )

    def record_policy_change(
        self,
        *,
        policy_id: UUID | None = None,
        policy_key: str | None = None,
        action: str,
        actor_id: UUID | None = None,
        tenant_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditRecord:
        resource_id = str(policy_id) if policy_id is not None else policy_key
        return self.record(
            event_type="policy.changed",
            actor_id=actor_id,
            tenant_id=tenant_id,
            resource_type="policy",
            resource_id=resource_id,
            outcome=action,
            request_id=request_id,
            metadata={
                **(metadata or {}),
                "policy_action": action,
                "policy_key": policy_key,
            },
            source="policy",
            category="governance",
        )

    def attach_event_bus(self, event_bus: EventBus) -> None:
        async def _handle(event: BaseEvent) -> None:
            self.record(
                event_type=event.name,
                metadata=event.payload,
                source="event_bus",
                category="integration",
            )

        event_bus.subscribe("*", _handle)
