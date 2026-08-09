from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.persistence.models import (
    ComparisonResultRecord,
    DiscoveryRunRecord,
    SnapshotRecord,
    SnapshotSource,
)
from backend.app.persistence.repositories import (
    FindingRepository,
    HistoryRepository,
    SnapshotRepository,
)


class DashboardRepositoryAdapter:
    """Adapt authoritative persisted history repositories for dashboard consumption."""

    def __init__(
        self,
        history_repository: HistoryRepository,
        snapshot_repository: SnapshotRepository,
        finding_repository: FindingRepository,
    ) -> None:
        self.history_repository = history_repository
        self.snapshot_repository = snapshot_repository
        self.finding_repository = finding_repository

    def list_discovery_runs(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> tuple[DiscoveryRunRecord, ...]:
        runs = self.history_repository.list_discovery_runs()
        return tuple(
            run
            for run in runs
            if self._filter_date(run.started_at, start, end)
            and self._matches_metadata(run.metadata_json or {}, metadata_filter)
        )

    def list_live_snapshots(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> tuple[SnapshotRecord, ...]:
        snapshots = self.snapshot_repository.list_by_source(SnapshotSource.LIVE)
        return tuple(
            snapshot
            for snapshot in snapshots
            if self._filter_date(snapshot.captured_at, start, end)
            and self._matches_metadata(
                getattr(snapshot.discovery_run, "metadata_json", {}) or {},
                metadata_filter,
            )
        )

    def list_comparison_results(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> tuple[ComparisonResultRecord, ...]:
        statement = (
            select(ComparisonResultRecord)
            .options(
                selectinload(ComparisonResultRecord.expected_snapshot).selectinload(
                    SnapshotRecord.discovery_run
                ),
                selectinload(ComparisonResultRecord.observed_snapshot),
                selectinload(ComparisonResultRecord.findings),
            )
            .order_by(ComparisonResultRecord.compared_at.desc())
        )
        comparisons = tuple(self.finding_repository.session.scalars(statement).all())
        return tuple(
            comparison
            for comparison in comparisons
            if self._filter_date(comparison.compared_at, start, end)
            and self._matches_metadata(
                getattr(comparison.expected_snapshot.discovery_run, "metadata_json", {})
                or {},
                metadata_filter,
            )
        )

    def get_latest_comparison_result(
        self,
        *,
        metadata_filter: dict[str, Any] | None = None,
    ) -> ComparisonResultRecord | None:
        comparisons = self.list_comparison_results(metadata_filter=metadata_filter)
        return comparisons[0] if comparisons else None

    def list_findings_for_comparison(
        self,
        comparison_id: UUID,
    ) -> tuple[Any, ...]:
        comparison = self.finding_repository.get_comparison_result(comparison_id)
        if comparison is None:
            return ()
        return tuple(comparison.findings)

    @staticmethod
    def _filter_date(
        value: datetime,
        start: datetime | None,
        end: datetime | None,
    ) -> bool:
        if start is not None and value < start:
            return False
        if end is not None and value > end:
            return False
        return True

    @staticmethod
    def _matches_metadata(
        metadata: dict[str, Any],
        filters: dict[str, Any] | None,
    ) -> bool:
        if filters is None:
            return True
        for key, value in filters.items():
            if value is None:
                continue
            if str(metadata.get(key)).lower() != str(value).lower():
                return False
        return True
