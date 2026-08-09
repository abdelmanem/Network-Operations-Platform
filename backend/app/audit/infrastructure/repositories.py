from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.audit.application.services import AuditRepository
from backend.app.audit.domain.models import AuditRecord
from backend.app.audit.infrastructure.models import AuditRecordModel


class SQLAlchemyAuditRepository(AuditRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

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
    ) -> AuditRecord:
        row = AuditRecordModel(
            event_type=event_type,
            actor_id=actor_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
            metadata_payload=json.dumps(metadata or {}),
            source=source,
            category=category,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return AuditRecord(
            id=row.id,
            event_type=row.event_type,
            timestamp=row.timestamp,
            actor_id=row.actor_id,
            tenant_id=row.tenant_id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            outcome=row.outcome,
            request_id=row.request_id,
            metadata=json.loads(row.metadata_payload or "{}"),
            source=row.source,
            category=row.category,
            created_at=row.created_at,
        )

    def list(self, *, limit: int = 50) -> list[AuditRecord]:
        rows = (
            self.session.query(AuditRecordModel)
            .order_by(AuditRecordModel.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            AuditRecord(
                id=row.id,
                event_type=row.event_type,
                timestamp=row.timestamp,
                actor_id=row.actor_id,
                tenant_id=row.tenant_id,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                outcome=row.outcome,
                request_id=row.request_id,
                metadata=json.loads(row.metadata_payload or "{}"),
                source=row.source,
                category=row.category,
                created_at=row.created_at,
            )
            for row in rows
        ]
