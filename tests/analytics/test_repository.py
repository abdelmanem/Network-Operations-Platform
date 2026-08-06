from __future__ import annotations

from backend.app.analytics.repository import HistoricalAnalyticsRepository
from tests.fixtures.analytics.golden_history import build_context


def test_repository_builds_context_from_history_entries() -> None:
    context = build_context()
    repository = HistoricalAnalyticsRepository(
        runs=context.runs,
        findings=context.findings,
    )

    rebuilt = repository.build_context()

    assert rebuilt.runs
    assert rebuilt.findings
    assert repository.list_runs() == context.runs
