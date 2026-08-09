from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.analytics.metadata import (
    AggregationGranularity as ServiceAggregationGranularity,
)
from backend.app.api.v1.dependencies import get_db_session
from backend.app.dashboard.repository import DashboardRepositoryAdapter
from backend.app.dashboard.service import DashboardService
from backend.app.persistence.repositories import (
    FindingRepository,
    HistoryRepository,
    SnapshotRepository,
)
from backend.app.schemas.dashboard import (
    DashboardAggregateBucketResponse,
    DashboardAggregatesRequest,
    DashboardAggregatesResponse,
    DashboardKpiRequest,
    DashboardKpiSummaryResponse,
    DashboardTrendEntryResponse,
    DashboardTrendsRequest,
    DashboardTrendsResponse,
    DashboardTrendsResponseEnvelope,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_dashboard_service(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> DashboardService:
    repository = DashboardRepositoryAdapter(
        history_repository=HistoryRepository(db_session),
        snapshot_repository=SnapshotRepository(db_session),
        finding_repository=FindingRepository(db_session),
    )
    return DashboardService(repository=repository)


@router.get(
    "/kpis",
    response_model=DashboardKpiSummaryResponse,
    summary="Get dashboard KPI summary",
)
def get_dashboard_kpis(
    payload: Annotated[DashboardKpiRequest, Depends()],
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> DashboardKpiSummaryResponse:
    summary = service.current_kpis(
        site=payload.site,
        device_role=payload.device_role,
        platform=payload.platform,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return DashboardKpiSummaryResponse(**asdict(summary))


@router.get(
    "/aggregates",
    response_model=DashboardAggregatesResponse,
    summary="Get dashboard aggregate statistics",
)
def get_dashboard_aggregates(
    payload: Annotated[DashboardAggregatesRequest, Depends()],
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> DashboardAggregatesResponse:
    items = service.aggregated_statistics(
        granularity=ServiceAggregationGranularity(payload.granularity.value),
        site=payload.site,
        device_role=payload.device_role,
        platform=payload.platform,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return DashboardAggregatesResponse(
        items=[DashboardAggregateBucketResponse(**asdict(item)) for item in items]
    )


@router.get(
    "/trends",
    response_model=DashboardTrendsResponseEnvelope,
    summary="Get dashboard trends",
)
def get_dashboard_trends(
    payload: Annotated[DashboardTrendsRequest, Depends()],
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> DashboardTrendsResponseEnvelope:
    trends = service.trends(
        site=payload.site,
        device_role=payload.device_role,
        platform=payload.platform,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return DashboardTrendsResponseEnvelope(
        trends=DashboardTrendsResponse(
            discovery_success_trend=DashboardTrendEntryResponse(
                **asdict(trends.discovery_success_trend)
            ),
            device_count_trend=DashboardTrendEntryResponse(
                **asdict(trends.device_count_trend)
            ),
            findings_count_trend=DashboardTrendEntryResponse(
                **asdict(trends.findings_count_trend)
            ),
            drift_trend=DashboardTrendEntryResponse(**asdict(trends.drift_trend)),
        )
    )
