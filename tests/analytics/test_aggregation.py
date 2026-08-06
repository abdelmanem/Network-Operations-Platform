from __future__ import annotations

from backend.app.analytics.aggregation import aggregate_runs
from backend.app.analytics.metadata import AggregationGranularity
from tests.fixtures.analytics.golden_history import build_context


def test_aggregate_runs_supports_weekly_buckets() -> None:
    context = build_context()

    buckets = aggregate_runs(context.runs, granularity=AggregationGranularity.WEEKLY)

    assert buckets
    assert buckets[0].count >= 1
    assert buckets[0].period_label
