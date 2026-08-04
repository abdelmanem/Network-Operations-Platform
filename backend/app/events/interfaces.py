"""Event publishing interfaces."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from backend.app.events.models import BaseEvent

EventHandler = Callable[[BaseEvent], Awaitable[None] | None]


@runtime_checkable
class EventPublisher(Protocol):
    """Protocol for event publishing."""

    async def publish(self, event: BaseEvent) -> None:
        """Publish an event."""
