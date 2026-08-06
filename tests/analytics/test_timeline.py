from __future__ import annotations

from backend.app.analytics.timeline import build_timeline
from tests.fixtures.analytics.golden_history import build_context


def test_build_timeline_includes_multiple_history_series() -> None:
    context = build_context()

    timeline = build_timeline(context)

    assert timeline
    assert any(entry.kind == "discovery" for entry in timeline)
    assert any(entry.kind == "finding" for entry in timeline)
