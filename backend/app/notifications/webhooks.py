"""Webhook delivery abstractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.notifications.models import NotificationMessage


@dataclass(slots=True)
class WebhookDeliveryRequest:
    """A normalized outbound webhook request."""

    url: str
    payload: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)


class WebhookDeliveryAdapter:
    """Port for delivering webhook requests."""

    async def deliver(self, request: WebhookDeliveryRequest) -> None:
        """Deliver a webhook request."""

        raise NotImplementedError


@dataclass(slots=True)
class RecordWebhookDeliveryAdapter(WebhookDeliveryAdapter):
    """In-memory delivery adapter for tests and local wiring."""

    requests: list[WebhookDeliveryRequest] = field(default_factory=list)

    async def deliver(self, request: WebhookDeliveryRequest) -> None:
        self.requests.append(request)


@dataclass(slots=True)
class WebhookNotificationChannelAdapter:
    """Webhook adapter that maps notification messages to webhook requests."""

    delivery: WebhookDeliveryAdapter

    async def deliver(self, message: NotificationMessage) -> None:
        request = WebhookDeliveryRequest(
            url=message.recipient,
            payload={
                "event": {
                    "name": message.event.name,
                    "payload": message.event.payload,
                    "occurred_at": message.event.occurred_at.isoformat(),
                },
                "message": message.body,
            },
            headers={"Content-Type": "application/json"},
        )
        await self.delivery.deliver(request)
