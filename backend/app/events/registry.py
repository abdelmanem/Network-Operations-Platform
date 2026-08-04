"""Event handler registration."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.events.interfaces import EventHandler


@dataclass(slots=True)
class EventHandlerRegistry:
    """Register event handlers against event names."""

    _handlers: dict[str, list[EventHandler]] = field(default_factory=dict)

    def register(self, event_name: str, handler: EventHandler) -> None:
        """Register a handler for an event name."""

        self._handlers.setdefault(event_name, []).append(handler)

    def handlers_for(self, event_name: str) -> tuple[EventHandler, ...]:
        """Return the handlers for an event."""

        return tuple(self._handlers.get(event_name, ()))

    def clear(self) -> None:
        """Remove all handlers."""

        self._handlers.clear()
