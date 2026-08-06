from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.history.findings import FindingHistory
from backend.app.persistence.models import FindingRecord
from backend.app.persistence.repositories import FindingRepository
from backend.app.schemas.findings import (
    EvidenceResponse,
    FindingResponse,
    FindingsListResponse,
)

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("", response_model=FindingsListResponse, summary="List findings")
def list_findings(
    db_session: Annotated[Session, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> FindingsListResponse:
    history = FindingHistory(FindingRepository(db_session))
    findings = history.list()
    start = (page - 1) * page_size
    end = start + page_size
    items = [_to_response(item) for item in findings[start:end]]
    return FindingsListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=len(findings),
        has_next=end < len(findings),
    )


@router.get("/{finding_id}", response_model=FindingResponse, summary="Get one finding")
def get_finding(
    finding_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> FindingResponse:
    history = FindingHistory(FindingRepository(db_session))
    findings = history.list()
    match = next((item for item in findings if item.id == finding_id), None)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )
    return _to_response(match)


def _to_response(record: FindingRecord) -> FindingResponse:
    return FindingResponse(
        id=record.id,
        finding_id=record.finding_id,
        rule_id=str(record.rule_id),
        title=record.title,
        severity=record.severity,
        description=record.description or "",
        expected_state=record.expected_state or {},
        observed_state=record.observed_state or {},
        evidence=[
            EvidenceResponse(
                id=evidence.id,
                source=evidence.source,
                description=evidence.description,
                reference=evidence.reference,
                details=evidence.details or {},
                captured_at=evidence.captured_at,
            )
            for evidence in getattr(record, "evidence", [])
        ],
        created_at=record.created_at,
    )
