import pytest
from backend.app.core.exceptions import UnsupportedNotificationChannelError
from backend.app.events.models import JobCompletedEvent, JobSubmittedEvent
from backend.app.notifications.email import (
    EmailNotificationChannelAdapter,
    RecordEmailAdapter,
)
from backend.app.notifications.models import NotificationMessage
from backend.app.notifications.service import NotificationService
from backend.app.notifications.webhooks import (
    RecordWebhookDeliveryAdapter,
    WebhookNotificationChannelAdapter,
)


class StubNotificationAdapter:
    def __init__(self) -> None:
        self.calls: list[NotificationMessage] = []

    async def deliver(self, notification: NotificationMessage) -> None:
        self.calls.append(notification)


@pytest.mark.anyio
async def test_notification_service_dispatches_to_registered_adapter() -> None:
    adapter = StubNotificationAdapter()
    service = NotificationService(
        adapters={"webhook": adapter},
        mappings=[("job.completed", "webhook")],
    )

    await service.dispatch(JobCompletedEvent(job_id="job-1", status="completed"))

    assert len(adapter.calls) == 1
    assert adapter.calls[0].channel == "webhook"
    assert adapter.calls[0].event.name == "job.completed"


@pytest.mark.anyio
async def test_notification_service_rejects_unregistered_channel() -> None:
    service = NotificationService(adapters={}, mappings=[("job.completed", "webhook")])

    with pytest.raises(UnsupportedNotificationChannelError):
        await service.dispatch(JobCompletedEvent(job_id="job-1", status="completed"))


@pytest.mark.anyio
async def test_webhook_channel_adapter_builds_payload_and_uses_delivery_adapter() -> (
    None
):
    delivery = RecordWebhookDeliveryAdapter()
    adapter = WebhookNotificationChannelAdapter(delivery)
    event = JobSubmittedEvent(job_id="job-2", status="submitted")
    message = NotificationMessage(
        channel="webhook",
        recipient="https://example.test/hook",
        subject="job submitted",
        body="submitted",
        event=event,
    )

    await adapter.deliver(message)

    assert len(delivery.requests) == 1
    assert delivery.requests[0].payload["event"]["name"] == "job.submitted"
    assert delivery.requests[0].url == "https://example.test/hook"


@pytest.mark.anyio
async def test_email_channel_adapter_uses_email_adapter_interface() -> None:
    email_adapter = RecordEmailAdapter()
    adapter = EmailNotificationChannelAdapter(email_adapter)
    event = JobCompletedEvent(job_id="job-3", status="completed")
    message = NotificationMessage(
        channel="email",
        recipient="ops@example.test",
        subject="job completed",
        body="completed",
        event=event,
    )

    await adapter.deliver(message)

    assert len(email_adapter.messages) == 1
    assert email_adapter.messages[0].recipient == "ops@example.test"
