from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Literal, cast

from backend.app.analytics.metadata import AggregationGranularity
from backend.app.analytics.trends import classify_trend
from backend.app.dashboard.models import (
    DashboardAggregateBucket,
    DashboardKpiSummary,
    DashboardTrendEntry,
    DashboardTrendsResponse,
)
from backend.app.dashboard.repository import DashboardRepositoryAdapter
from backend.app.persistence.models import ComparisonResultRecord


class DashboardService:
    """Compose dashboard KPIs, aggregates, and trends from persisted history."""

    def __init__(
        self,
        repository: DashboardRepositoryAdapter,
    ) -> None:
        self.repository = repository

    def current_kpis(
        self,
        *,
        site: str | None = None,
        device_role: str | None = None,
        platform: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> DashboardKpiSummary:
        filters = self._build_metadata_filter(site, device_role, platform)
        live_snapshots = self.repository.list_live_snapshots(
            start=start_date,
            end=end_date,
            metadata_filter=filters,
        )
        comparison = self.repository.get_latest_comparison_result(
            metadata_filter=filters,
        )

        unsupported = self._unsupported_kpis()

        latest_live = live_snapshots[0] if live_snapshots else None
        live_devices = latest_live.devices if latest_live is not None else None

        total_devices = len(live_devices) if live_devices is not None else None
        reachable_devices = len(live_devices) if live_devices is not None else None

        missing_devices = None
        extra_devices = None
        modified_devices = None
        findings_total = None
        critical_findings = None
        major_findings = None
        minor_findings = None
        netbox_accuracy_pct = None

        if comparison is not None:
            metrics = comparison.metrics or {}
            missing_devices = metrics.get("missing")
            extra_devices = metrics.get("unexpected")
            modified_devices = metrics.get("modified")
            findings_total = metrics.get("total_findings")
            critical_findings, major_findings, minor_findings = self._count_severity(
                comparison.findings
            )
            netbox_accuracy_pct = self._netbox_accuracy_from_comparison(
                comparison, total_devices
            )

        return DashboardKpiSummary(
            total_devices=total_devices,
            reachable_devices=reachable_devices,
            unreachable_devices=None,
            discovery_success_pct=None,
            netbox_accuracy_pct=netbox_accuracy_pct,
            missing_devices=missing_devices,
            extra_devices=extra_devices,
            modified_devices=modified_devices,
            findings_total=findings_total,
            critical_findings=critical_findings,
            major_findings=major_findings,
            minor_findings=minor_findings,
            latest_run_id=None,
            latest_run_started_at=None,
            latest_run_finished_at=None,
            unsupported_metrics=tuple(unsupported),
        )

    def aggregated_statistics(
        self,
        *,
        granularity: AggregationGranularity = AggregationGranularity.DAILY,
        site: str | None = None,
        device_role: str | None = None,
        platform: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[DashboardAggregateBucket, ...]:
        filters = self._build_metadata_filter(site, device_role, platform)
        comparisons = self.repository.list_comparison_results(
            start=start_date,
            end=end_date,
            metadata_filter=filters,
        )

        if not comparisons:
            return ()

        buckets: dict[tuple[str, datetime, datetime], DashboardAggregateBucket] = {}
        for comparison in reversed(comparisons):
            label = self._bucket_label(comparison.compared_at, granularity)
            start = self._bucket_start(comparison.compared_at, granularity)
            end = self._bucket_end(comparison.compared_at, granularity)
            key = (label, start, end)
            bucket = buckets.get(key)
            metrics = comparison.metrics or {}
            if bucket is None:
                bucket = DashboardAggregateBucket(
                    period_label=label,
                    start=start,
                    end=end,
                    discovery_success_pct=None,
                    total_devices=(
                        len(comparison.observed_snapshot.devices)
                        if comparison.observed_snapshot is not None
                        else None
                    ),
                    missing_devices=metrics.get("missing"),
                    extra_devices=metrics.get("unexpected"),
                    modified_devices=metrics.get("modified"),
                    findings_total=metrics.get("total_findings"),
                )
                buckets[key] = bucket
                continue

            bucket.missing_devices = self._sum_nullable(
                bucket.missing_devices, metrics.get("missing")
            )
            bucket.extra_devices = self._sum_nullable(
                bucket.extra_devices, metrics.get("unexpected")
            )
            bucket.modified_devices = self._sum_nullable(
                bucket.modified_devices, metrics.get("modified")
            )
            bucket.findings_total = self._sum_nullable(
                bucket.findings_total, metrics.get("total_findings")
            )
            latest_devices = (
                len(comparison.observed_snapshot.devices)
                if comparison.observed_snapshot is not None
                else None
            )
            if latest_devices is not None:
                bucket.total_devices = latest_devices

        return tuple(sorted(buckets.values(), key=lambda item: item.start))

    def trends(
        self,
        *,
        site: str | None = None,
        device_role: str | None = None,
        platform: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> DashboardTrendsResponse:
        filters = self._build_metadata_filter(site, device_role, platform)
        comparisons = self.repository.list_comparison_results(
            start=start_date,
            end=end_date,
            metadata_filter=filters,
        )

        device_series = self._extract_device_count_series(comparisons)
        findings_series = self._extract_findings_count_series(comparisons)
        drift_series = self._extract_drift_series(comparisons)

        return DashboardTrendsResponse(
            discovery_success_trend=self._build_trend_entry(
                "discovery_success",
                [],
                start_date,
                end_date,
            ),
            device_count_trend=self._build_trend_entry(
                "device_count",
                device_series,
                start_date,
                end_date,
            ),
            findings_count_trend=self._build_trend_entry(
                "findings_count",
                findings_series,
                start_date,
                end_date,
            ),
            drift_trend=self._build_trend_entry(
                "drift",
                drift_series,
                start_date,
                end_date,
            ),
        )

    def _unsupported_kpis(self) -> list[str]:
        return [
            "successful_targets",
            "failed_targets",
            "skipped_targets",
            "total_targets",
            "discovery_success_pct",
            "unreachable_devices",
        ]

    def _build_metadata_filter(
        self,
        site: str | None,
        device_role: str | None,
        platform: str | None,
    ) -> dict[str, Any] | None:
        filters: dict[str, Any] = {}
        if site is not None:
            filters["site"] = site
        if device_role is not None:
            filters["device_role"] = device_role
        if platform is not None:
            filters["platform"] = platform
        return filters or None

    def _count_severity(
        self,
        findings: Sequence[Any],
    ) -> tuple[int | None, int | None, int | None]:
        critical = 0
        major = 0
        minor = 0
        for finding in findings:
            severity = getattr(finding, "severity", None)
            if severity is None:
                continue
            if str(severity).lower() == "critical":
                critical += 1
            elif str(severity).lower() == "high":
                major += 1
            else:
                minor += 1
        return critical, major, minor

    def _netbox_accuracy_from_comparison(
        self,
        comparison: ComparisonResultRecord,
        total_devices: int | None,
    ) -> float | None:
        metrics = comparison.metrics or {}
        if total_devices is None or total_devices == 0:
            return None
        missing = metrics.get("missing")
        modified = metrics.get("modified")
        if missing is None or modified is None:
            return None
        try:
            missing_value = int(missing)
            modified_value = int(modified)
        except (TypeError, ValueError):
            return None
        accurate = max(total_devices - missing_value - modified_value, 0)
        return round((accurate / total_devices) * 100.0, 2)

    def _extract_device_count_series(
        self,
        comparisons: Sequence[ComparisonResultRecord],
    ) -> list[int]:
        values: list[int] = []
        for comparison in reversed(comparisons):
            observed_snapshot = comparison.observed_snapshot
            if observed_snapshot is None:
                continue
            values.append(len(observed_snapshot.devices))
        return values

    def _extract_findings_count_series(
        self,
        comparisons: Sequence[ComparisonResultRecord],
    ) -> list[int]:
        return [len(comparison.findings) for comparison in reversed(comparisons)]

    def _extract_drift_series(
        self,
        comparisons: Sequence[ComparisonResultRecord],
    ) -> list[int]:
        values: list[int] = []
        for comparison in reversed(comparisons):
            metrics = comparison.metrics or {}
            drift = 0
            if metrics.get("missing") is not None:
                drift += metrics["missing"]
            if metrics.get("unexpected") is not None:
                drift += metrics["unexpected"]
            if metrics.get("modified") is not None:
                drift += metrics["modified"]
            values.append(drift)
        return values

    def _build_trend_entry(
        self,
        metric: str,
        values: Sequence[float | int],
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> DashboardTrendEntry:
        trend = cast(
            Literal["stable", "increasing", "decreasing", "volatile"],
            classify_trend(list(values)),
        )
        direction = self._trend_direction(values)
        return DashboardTrendEntry(
            metric=metric,
            baseline_value=values[0] if values else None,
            current_value=values[-1] if values else None,
            trend=trend,
            direction=direction,
            period_start=start_date,
            period_end=end_date,
        )

    def _trend_direction(
        self,
        values: Sequence[float | int],
    ) -> Literal["up", "down", "flat"]:
        if len(values) < 2:
            return "flat"
        if values[-1] > values[0]:
            return "up"
        if values[-1] < values[0]:
            return "down"
        return "flat"

    def _bucket_label(
        self,
        timestamp: datetime,
        granularity: AggregationGranularity,
    ) -> str:
        if granularity is AggregationGranularity.WEEKLY:
            return timestamp.strftime("%Y-W%U")
        if granularity is AggregationGranularity.MONTHLY:
            return timestamp.strftime("%Y-%m")
        return timestamp.strftime("%Y-%m-%d")

    def _bucket_start(
        self,
        timestamp: datetime,
        granularity: AggregationGranularity,
    ) -> datetime:
        if granularity is AggregationGranularity.WEEKLY:
            return timestamp - timedelta(days=timestamp.weekday())
        if granularity is AggregationGranularity.MONTHLY:
            return timestamp.replace(day=1)
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

    def _bucket_end(
        self,
        timestamp: datetime,
        granularity: AggregationGranularity,
    ) -> datetime:
        if granularity is AggregationGranularity.WEEKLY:
            return self._bucket_start(timestamp, granularity) + timedelta(
                days=6,
                hours=23,
                minutes=59,
                seconds=59,
                microseconds=999999,
            )
        if granularity is AggregationGranularity.MONTHLY:
            next_month = (timestamp.replace(day=28) + timedelta(days=4)).replace(day=1)
            return next_month - timedelta(microseconds=1)
        return self._bucket_start(timestamp, granularity) + timedelta(
            days=1,
            microseconds=-1,
        )

    @staticmethod
    def _sum_nullable(value: int | None, addition: int | None) -> int | None:
        if value is None:
            return addition
        if addition is None:
            return value
        return value + addition
