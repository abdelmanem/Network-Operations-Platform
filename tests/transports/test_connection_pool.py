from dataclasses import dataclass

import pytest
from backend.app.transports.connection_pool import ConnectionPool
from backend.app.transports.session import TransportSession


@dataclass(slots=True)
class DummySession(TransportSession):
    async def close(self) -> None:
        self.mark_closed()


@pytest.mark.anyio
async def test_connection_pool_reuses_sessions() -> None:
    pool = ConnectionPool(max_size=2)
    created: list[DummySession] = []

    def factory() -> DummySession:
        session = DummySession(session_id="session-1")
        created.append(session)
        return session

    first = await pool.get_or_create("key", factory)
    second = await pool.get_or_create("key", factory)

    assert first is second
    assert first.is_open is True
    assert len(created) == 1

    await pool.release("key")
    assert first.is_open is False
