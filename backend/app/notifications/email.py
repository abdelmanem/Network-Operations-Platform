"""Email adapter abstractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.notifications.models import NotificationMessage


@dataclass(slots=True)
class EmailMessage:
    """Normalized email payload."""

    recipient: str
    subject: str
    body: str
    metadata: dict[str, Any] = field(default_factory=dict)


class EmailAdapter:
    """Port for sending emails without binding the domain to SMTP."""

    async def send(self, message: EmailMessage) -> None:
        """Send an email message."""

        raise NotImplementedError


@dataclass(slots=True)
class RecordEmailAdapter(EmailAdapter):
    """In-memory email adapter for tests and local wiring."""

    messages: list[EmailMessage] = field(default_factory=list)

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


@dataclass(slots=True)
class EmailNotificationChannelAdapter:
    """Email adapter that maps notifications to a lower-level email port."""

    email_adapter: EmailAdapter

    async def deliver(self, message: NotificationMessage) -> None:
        email_message = EmailMessage(
            recipient=message.recipient,
            subject=message.subject,
            body=message.body,
            metadata={"event_name": message.event.name},
        )
        await self.email_adapter.send(email_message)
