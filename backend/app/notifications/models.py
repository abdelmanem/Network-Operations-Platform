"""Notification model abstractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.events.models import BaseEvent


@dataclass(slots=True)
class NotificationMessage:
    """A normalized notification message emitted by the domain layer."""

    channel: str
    recipient: str
    subject: str
    body: str
    event: BaseEvent
    metadata: dict[str, Any] = field(default_factory=dict)
