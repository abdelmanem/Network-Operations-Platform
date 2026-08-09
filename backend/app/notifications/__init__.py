"""Notification abstractions for domain events."""

from backend.app.notifications.email import (
    EmailAdapter,
    EmailMessage,
    EmailNotificationChannelAdapter,
)
from backend.app.notifications.models import NotificationMessage
from backend.app.notifications.service import NotificationService
from backend.app.notifications.webhooks import (
    WebhookDeliveryAdapter,
    WebhookDeliveryRequest,
    WebhookNotificationChannelAdapter,
)

__all__ = [
    "EmailAdapter",
    "EmailMessage",
    "EmailNotificationChannelAdapter",
    "NotificationMessage",
    "NotificationService",
    "WebhookDeliveryAdapter",
    "WebhookDeliveryRequest",
    "WebhookNotificationChannelAdapter",
]
