from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.history.discovery import DiscoveryHistory
from backend.app.persistence.models import DiscoveryRunRecord
from backend.app.persistence.repositories import HistoryRepository
from backend.app.schemas.discovery import DiscoveryRunListResponse, DiscoveryRunSummary

router = APIRouter(prefix="/history", tags=["history"])


@router.get(
    "/discovery-runs",
    response_model=DiscoveryRunListResponse,
    summary="List discovery run history",
)
def list_discovery_runs(
    db_session: Annotated[Session, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> DiscoveryRunListResponse:
    history = DiscoveryHistory(HistoryRepository(db_session))
    runs = history.list()
    start = (page - 1) * page_size
    end = start + page_size
    items = [_to_summary(item) for item in runs[start:end]]
    return DiscoveryRunListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=len(runs),
        has_next=end < len(runs),
    )


def _to_summary(record: DiscoveryRunRecord) -> DiscoveryRunSummary:
    return DiscoveryRunSummary(
        id=record.id,
        target_identifier=record.target_identifier,
        target_address=record.target_address,
        status=record.status,
        metadata=record.metadata_json or {},
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )
