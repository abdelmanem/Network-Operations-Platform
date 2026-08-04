from dataclasses import dataclass

from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
)
from backend.app.transports.registry import TransportRegistry
from backend.app.transports.session import TransportSession


@dataclass(slots=True)
class DummySession(TransportSession):
    async def close(self) -> None:
        self.mark_closed()


class DummyTransport(BaseTransport):
    name = "dummy"
    capabilities = frozenset({TransportCapability.SSH})

    def health_check(self, context: TransportContext) -> None:
        return None

    def create_session(self, context: TransportContext) -> TransportSession:
        return DummySession(session_id=context.target.identifier)

    def close(self) -> None:
        return None


def test_transport_registry_registers_and_selects_transports() -> None:
    registry = TransportRegistry()
    transport = DummyTransport()

    registry.register(transport)

    assert registry.get("dummy") is transport
    assert registry.select(frozenset({TransportCapability.SSH})) == (transport,)
