from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.auth.api.dependencies import require_permission
from backend.app.auth.domain.models import User
from backend.app.comparison.snapshot_service import (
    SnapshotComparisonError,
    SnapshotComparisonService,
)
from backend.app.persistence.models import ComparisonResultRecord
from backend.app.persistence.repositories import FindingRepository
from backend.app.schemas.comparison import (
    ComparisonResultResponse,
    SnapshotComparisonRequest,
)

router = APIRouter(tags=["comparison"])


@router.post(
    "/comparison",
    response_model=ComparisonResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compare existing expected and observed snapshots",
)
def compare_existing_snapshots(
    payload: SnapshotComparisonRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("inventory:write"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> ComparisonResultResponse:
    """Persist the existing comparison result for tenant-accessible snapshots."""

    try:
        result_id = SnapshotComparisonService(db_session).compare(
            expected_snapshot_id=payload.expected_snapshot_id,
            observed_snapshot_id=payload.observed_snapshot_id,
            tenant_id=tenant_id,
        )
    except SnapshotComparisonError as exc:
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    record = FindingRepository(db_session).get_comparison_result(result_id)
    if record is None:  # pragma: no cover - committed record must be readable
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return _comparison_response(record)


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
    return _comparison_response(record)


def _comparison_response(record: ComparisonResultRecord) -> ComparisonResultResponse:
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
