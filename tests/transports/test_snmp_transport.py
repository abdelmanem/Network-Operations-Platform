"""Tests for the concrete SNMP transport adapter."""

from __future__ import annotations

import asyncio

from backend.app.transports import (
    PySnmpTransport,
    TransportContext,
    TransportRetryPolicy,
    TransportTarget,
)


class _FakeSnmpModule:
    class SnmpEngine:
        pass

    class CommunityData:
        def __init__(self, community: str) -> None:
            self.community = community

    class UdpTransportTarget:
        def __init__(
            self,
            endpoint: tuple[str, int],
            *,
            timeout: float | None,
            retries: int,
        ) -> None:
            self.endpoint = endpoint
            self.timeout = timeout
            self.retries = retries

    class ContextData:
        pass

    class ObjectIdentity:
        def __init__(self, oid: str) -> None:
            self.oid = oid

    class ObjectType:
        def __init__(self, identity: object) -> None:
            self.identity = identity

    async def get_cmd(
        self, *args: object, **kwargs: object
    ) -> tuple[None, None, None, list[tuple[str, int]]]:
        return None, None, None, [("1.3.6.1.2.1.1.1.0", 42)]

    async def next_cmd(
        self, *args: object, **kwargs: object
    ) -> tuple[None, None, None, list[list[tuple[str, int]]]]:
        return None, None, None, [[("1.3.6.1.2.1.1.1.0", 42)]]


def test_snmp_transport_get_and_walk(monkeypatch: object) -> None:
    monkeypatch.setattr(
        "backend.app.transports.snmp.pysnmp._pysnmp_asyncio",
        lambda: _FakeSnmpModule(),
    )

    transport = PySnmpTransport()
    context = TransportContext(
        target=TransportTarget(identifier="switch-3", address="10.0.0.3"),
        metadata={"community": "public"},
        retry_policy=TransportRetryPolicy(max_attempts=2),
    )
    session = transport.create_session(context)

    async def run() -> None:
        await session.open()
        oid, value = await session.get("1.3.6.1.2.1.1.1.0")
        walk = await session.walk("1.3.6.1.2.1.1")
        await session.close()
        assert oid == "1.3.6.1.2.1.1.1.0"
        assert value == 42
        assert walk == [("1.3.6.1.2.1.1.1.0", 42)]

    asyncio.run(run())
