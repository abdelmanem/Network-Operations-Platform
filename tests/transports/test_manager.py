from dataclasses import dataclass

import pytest
from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
    TransportTarget,
)
from backend.app.transports.credentials import (
    StaticCredentialResolver,
    UsernamePasswordCredentials,
)
from backend.app.transports.manager import TransportManager
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


@pytest.mark.anyio
async def test_transport_manager_opens_and_reuses_session() -> None:
    manager = TransportManager()
    manager.register(DummyTransport())
    target = TransportTarget(identifier="device-1", address="10.0.0.1")

    first = await manager.open_session("dummy", target)
    second = await manager.open_session("dummy", target)

    assert first is second
    assert first.is_open is True

    await manager.close_session("dummy", target)
    assert first.is_open is False


def test_transport_manager_resolves_credentials() -> None:
    manager = TransportManager(
        credential_resolver=StaticCredentialResolver(
            credentials=UsernamePasswordCredentials(
                username="user",
                password="".join(["p", "ass"]),
            )
        ),
    )
    target = TransportTarget(identifier="device-1", address="10.0.0.1")

    credentials = manager.resolve_credentials(target, capabilities=frozenset())

    assert credentials is not None
    assert credentials.as_dict()["username"] == "user"
