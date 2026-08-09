from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.audit.application.services import AuditService
from backend.app.audit.infrastructure.repositories import SQLAlchemyAuditRepository
from backend.app.database.session import get_db_session

router = APIRouter(prefix="/audit", tags=["audit"])


def get_audit_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> AuditService:
    repository = SQLAlchemyAuditRepository(db)
    return AuditService(repository=repository)


@router.get("/records")
def list_records(
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> list[dict[str, object]]:
    repository = audit_service._repository_instance()
    records = repository.list(limit=20) if repository is not None else []
    return [
        {
            "event_type": record.event_type,
            "timestamp": record.timestamp.isoformat(),
            "actor_id": str(record.actor_id) if record.actor_id is not None else None,
            "tenant_id": record.tenant_id,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "outcome": record.outcome,
            "request_id": record.request_id,
            "metadata": record.metadata,
            "source": record.source,
            "category": record.category,
        }
        for record in records
    ]
