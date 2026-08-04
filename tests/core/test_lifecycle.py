import pytest
from backend.app.core.lifecycle import ApplicationLifecycleManager


@pytest.mark.anyio
async def test_lifecycle_hooks_run_in_order() -> None:
    manager = ApplicationLifecycleManager()
    calls: list[str] = []

    def sync_startup() -> None:
        calls.append("startup-sync")

    async def async_shutdown() -> None:
        calls.append("shutdown-async")

    manager.register_startup(sync_startup)
    manager.register_shutdown(async_shutdown)

    await manager.startup()
    await manager.shutdown()

    assert calls == ["startup-sync", "shutdown-async"]
