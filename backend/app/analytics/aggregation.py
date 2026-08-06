"""Aggregation helpers for historical analytics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.app.analytics.context import HistoricalRunEntry
from backend.app.analytics.metadata import AggregationBucket, AggregationGranularity


@dataclass(frozen=True, slots=True)
class AggregationResult:
    """Aggregated time bucket for historical analytics."""

    start: datetime
    end: datetime
    period_label: str
    count: int
    compliance_score: float
    risk_score: float
    discovered_devices: int


def aggregate_runs(
    runs: Iterable[HistoricalRunEntry],
    *,
    granularity: AggregationGranularity = AggregationGranularity.DAILY,
    start: datetime | None = None,
    end: datetime | None = None,
    rolling_window: int | None = None,
) -> tuple[AggregationBucket, ...]:
    """Aggregate run metrics into time buckets."""

    ordered_runs = sorted(runs, key=lambda run: run.started_at)
    if not ordered_runs:
        return ()

    window = rolling_window or 1
    buckets: list[AggregationBucket] = []
    cursor = start or ordered_runs[0].started_at
    final = end or ordered_runs[-1].started_at

    while cursor <= final:
        bucket_end = _bucket_end(cursor, granularity)
        bucket_runs = [
            run
            for run in ordered_runs
            if start is not None or run.started_at >= cursor
            if end is not None or run.started_at < bucket_end
        ]
        if rolling_window is not None:
            bucket_runs = _rolling_window(bucket_runs, window)
        if bucket_runs:
            bucket = AggregationBucket(
                granularity=granularity,
                start=cursor,
                end=bucket_end,
                period_label=_period_label(cursor, granularity),
                count=len(bucket_runs),
                compliance_score=(
                    sum(float(run.compliance_score) for run in bucket_runs)
                    / len(bucket_runs)
                ),
                risk_score=(
                    sum(float(run.risk_score or 0.0) for run in bucket_runs)
                    / len(bucket_runs)
                ),
                discovered_devices=sum(run.discovered_devices for run in bucket_runs),
            )
            buckets.append(bucket)
        cursor = bucket_end + timedelta(microseconds=1)

    return tuple(buckets)


def _bucket_end(value: datetime, granularity: AggregationGranularity) -> datetime:
    if granularity is AggregationGranularity.WEEKLY:
        return value + timedelta(days=6)
    if granularity is AggregationGranularity.MONTHLY:
        return value.replace(day=28) + timedelta(days=4)
    if granularity is AggregationGranularity.QUARTERLY:
        quarter_end = (value.month - 1) // 3 * 3 + 3
        return value.replace(month=quarter_end, day=28) + timedelta(days=4)
    if granularity is AggregationGranularity.YEARLY:
        return value.replace(month=12, day=31)
    return value


def _period_label(value: datetime, granularity: AggregationGranularity) -> str:
    if granularity is AggregationGranularity.WEEKLY:
        return value.strftime("%Y-W%U")
    if granularity is AggregationGranularity.MONTHLY:
        return value.strftime("%Y-%m")
    if granularity is AggregationGranularity.QUARTERLY:
        return value.strftime("%Y-Q%q")
    if granularity is AggregationGranularity.YEARLY:
        return value.strftime("%Y")
    return value.strftime("%Y-%m-%d")


def _rolling_window(
    runs: list[HistoricalRunEntry],
    window: int,
) -> list[HistoricalRunEntry]:
    if len(runs) <= window:
        return runs
    return runs[-window:]
