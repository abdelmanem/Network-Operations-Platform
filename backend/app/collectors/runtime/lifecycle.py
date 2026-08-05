"""Collector runtime lifecycle hooks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

LifecycleHook = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class CollectorRuntimeLifecycle:
    """Manage runtime startup and shutdown hooks."""

    startup_hooks: list[LifecycleHook] = field(default_factory=list)
    shutdown_hooks: list[LifecycleHook] = field(default_factory=list)
    started: bool = False

    def on_startup(self, hook: LifecycleHook) -> None:
        """Register a startup hook."""

        self.startup_hooks.append(hook)

    def on_shutdown(self, hook: LifecycleHook) -> None:
        """Register a shutdown hook."""

        self.shutdown_hooks.append(hook)

    async def start(self) -> None:
        """Run startup hooks."""

        for hook in self.startup_hooks:
            await hook()
        self.started = True

    async def stop(self) -> None:
        """Run shutdown hooks."""

        for hook in reversed(self.shutdown_hooks):
            await hook()
        self.started = False
