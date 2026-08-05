from __future__ import annotations

import pytest
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.scheduler import CollectorScheduler
from backend.app.discovery.context import DiscoveryTarget


@pytest.mark.anyio
async def test_scheduler_orders_jobs_by_priority() -> None:
    scheduler = CollectorScheduler()
    high = CollectorRuntimeContext(
        target=DiscoveryTarget(identifier="device-1", address="10.0.0.1")
    )
    low = CollectorRuntimeContext(
        target=DiscoveryTarget(identifier="device-2", address="10.0.0.2")
    )

    await scheduler.schedule(low, priority=10)
    await scheduler.schedule(high, priority=0)

    first = await scheduler.next_job()
    second = await scheduler.next_job()

    assert first.context.target.identifier == "device-1"
    assert second.context.target.identifier == "device-2"
