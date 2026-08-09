"""Event bus facade for publishing and subscription."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.events.dispatcher import EventDispatcher
from backend.app.events.interfaces import EventHandler, EventPublisher
from backend.app.events.models import BaseEvent
from backend.app.events.registry import EventHandlerRegistry


@dataclass(slots=True)
class EventBus(EventPublisher):
    """Coordinate event registration and publication through a dispatcher."""

    registry: EventHandlerRegistry = field(default_factory=EventHandlerRegistry)
    dispatcher: EventDispatcher = field(init=False)

    def __post_init__(self) -> None:
        self.dispatcher = EventDispatcher(self.registry)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register a handler for an event name."""

        self.registry.register(event_name, handler)

    async def publish(self, event: BaseEvent) -> None:
        """Publish an event to all registered handlers."""

        await self.dispatcher.publish(event)
