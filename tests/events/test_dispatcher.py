import pytest
from backend.app.core.exceptions import EventError
from backend.app.events.dispatcher import EventDispatcher
from backend.app.events.models import BaseEvent
from backend.app.events.registry import EventHandlerRegistry


@pytest.mark.anyio
async def test_event_dispatcher_invokes_handlers() -> None:
    registry = EventHandlerRegistry()
    dispatcher = EventDispatcher(registry)
    calls: list[str] = []

    def sync_handler(event: BaseEvent) -> None:
        calls.append(event.name)

    async def async_handler(event: BaseEvent) -> None:
        calls.append(f"async:{event.name}")

    registry.register("demo.event", sync_handler)
    registry.register("demo.event", async_handler)

    await dispatcher.publish(BaseEvent(name="demo.event"))

    assert calls == ["demo.event", "async:demo.event"]


@pytest.mark.anyio
async def test_event_dispatcher_isolates_handler_failures() -> None:
    registry = EventHandlerRegistry()
    dispatcher = EventDispatcher(registry)
    calls: list[str] = []

    def failing_handler(event: BaseEvent) -> None:
        calls.append(f"failed:{event.name}")
        raise RuntimeError("boom")

    def successful_handler(event: BaseEvent) -> None:
        calls.append(f"ok:{event.name}")

    registry.register("demo.event", failing_handler)
    registry.register("demo.event", successful_handler)

    with pytest.raises(EventError):
        await dispatcher.publish(BaseEvent(name="demo.event"))

    assert calls == ["failed:demo.event", "ok:demo.event"]
