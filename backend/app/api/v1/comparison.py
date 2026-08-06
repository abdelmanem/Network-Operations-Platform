from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.persistence.repositories import FindingRepository
from backend.app.schemas.comparison import ComparisonResultResponse

router = APIRouter(tags=["comparison"])


@router.get(
    "/comparison/{run_id}",
    response_model=ComparisonResultResponse,
    summary="Get comparison result",
)
def get_comparison_result(
    run_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> ComparisonResultResponse:
    repository = FindingRepository(db_session)
    record = repository.get_comparison_result(run_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comparison result not found"
        )
    return ComparisonResultResponse(
        id=record.id,
        expected_snapshot_id=record.expected_snapshot_id,
        observed_snapshot_id=record.observed_snapshot_id,
        compared_at=record.compared_at,
        metrics=record.metrics or {},
        findings=[
            {"id": finding.id, "rule_id": finding.rule_id}
            for finding in record.findings
        ],
    )
