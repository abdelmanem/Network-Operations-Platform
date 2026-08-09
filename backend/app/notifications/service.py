"""Application notification service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from backend.app.core.exceptions import UnsupportedNotificationChannelError
from backend.app.events.models import BaseEvent
from backend.app.notifications.models import NotificationMessage


class SupportsDelivery(Protocol):
    """Minimal protocol for notification channel adapters."""

    async def deliver(self, notification: NotificationMessage) -> None:
        """Deliver a notification message."""


NotificationChannelAdapter = (
    Callable[[NotificationMessage], Awaitable[None]] | SupportsDelivery
)


@dataclass(slots=True)
class NotificationService:
    """Dispatch normalized notifications to channel-specific adapters."""

    adapters: dict[str, NotificationChannelAdapter] = field(default_factory=dict)
    mappings: list[tuple[str, str]] = field(default_factory=list)

    def _resolve_channel(self, event: BaseEvent) -> str:
        for event_name, channel in self.mappings:
            if event_name == event.name:
                return channel
        raise UnsupportedNotificationChannelError(
            f"No notification channel registered for event '{event.name}'."
        )

    async def dispatch(self, event: BaseEvent) -> None:
        """Dispatch a domain event to a registered channel adapter."""

        channel = self._resolve_channel(event)
        adapter = self.adapters.get(channel)
        if adapter is None:
            raise UnsupportedNotificationChannelError(
                f"Notification channel '{channel}' is not registered."
            )

        message = NotificationMessage(
            channel=channel,
            recipient="",
            subject=event.name,
            body=str(event.payload),
            event=event,
            metadata={"event_name": event.name},
        )
        if callable(adapter):
            await adapter(message)
        else:
            await adapter.deliver(message)

    def register_mapping(self, event_name: str, channel: str) -> None:
        """Register an event-to-channel mapping."""

        self.mappings.append((event_name, channel))
