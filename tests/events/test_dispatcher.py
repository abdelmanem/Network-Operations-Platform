import pytest
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
