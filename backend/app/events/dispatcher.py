"""Event dispatcher implementation."""

from __future__ import annotations

from dataclasses import dataclass
from inspect import isawaitable

from backend.app.core.exceptions import EventError
from backend.app.events.interfaces import EventPublisher
from backend.app.events.models import BaseEvent
from backend.app.events.registry import EventHandlerRegistry


@dataclass(slots=True)
class EventDispatcher(EventPublisher):
    """Dispatch events to registered handlers."""

    registry: EventHandlerRegistry

    async def publish(self, event: BaseEvent) -> None:
        """Publish an event to all matching handlers."""

        errors: list[Exception] = []
        for handler in self.registry.handlers_for(event.name):
            try:
                result = handler(event)
                if isawaitable(result):
                    await result
            except Exception as exc:  # pragma: no cover - defensive guard
                errors.append(exc)

        if errors:
            raise EventError(f"Failed to dispatch event '{event.name}'.") from errors[0]
