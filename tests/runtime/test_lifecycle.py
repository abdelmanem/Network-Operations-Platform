from __future__ import annotations

import pytest
from backend.app.collectors.runtime.lifecycle import CollectorRuntimeLifecycle


@pytest.mark.anyio
async def test_lifecycle_runs_hooks_in_order() -> None:
    lifecycle = CollectorRuntimeLifecycle()
    events: list[str] = []

    async def start_hook() -> None:
        events.append("start")

    async def stop_hook() -> None:
        events.append("stop")

    lifecycle.on_startup(start_hook)
    lifecycle.on_shutdown(stop_hook)

    await lifecycle.start()
    await lifecycle.stop()

    assert events == ["start", "stop"]
    assert lifecycle.started is False
