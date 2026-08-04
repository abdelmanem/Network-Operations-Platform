"""Application lifecycle management."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from backend.app.core.exceptions import LifecycleError

LifecycleHook = Callable[[], Awaitable[None] | None]


@dataclass(slots=True)
class ApplicationLifecycleManager:
    """Register and execute startup and shutdown hooks."""

    startup_hooks: list[LifecycleHook] = field(default_factory=list)
    shutdown_hooks: list[LifecycleHook] = field(default_factory=list)

    def register_startup(self, hook: LifecycleHook) -> None:
        """Register a startup hook."""

        self.startup_hooks.append(hook)

    def register_shutdown(self, hook: LifecycleHook) -> None:
        """Register a shutdown hook."""

        self.shutdown_hooks.append(hook)

    async def startup(self) -> None:
        """Execute startup hooks in registration order."""

        await self._run_hooks(self.startup_hooks)

    async def shutdown(self) -> None:
        """Execute shutdown hooks in reverse registration order."""

        await self._run_hooks(reversed(self.shutdown_hooks))

    @staticmethod
    async def _run_hooks(hooks: Iterable[LifecycleHook]) -> None:
        for hook in hooks:
            try:
                result = hook()
                if result is not None:
                    await result
            except Exception as exc:  # pragma: no cover - defensive guard
                raise LifecycleError("Application lifecycle hook failed.") from exc


@asynccontextmanager
async def lifecycle_context(
    lifecycle_manager: ApplicationLifecycleManager,
) -> AsyncIterator[None]:
    """Wrap application lifecycle hooks in a FastAPI lifespan context."""

    await lifecycle_manager.startup()
    try:
        yield
    finally:
        await lifecycle_manager.shutdown()
