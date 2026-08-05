from __future__ import annotations

from dataclasses import dataclass

import pytest
from backend.app.collectors.cisco import (
    CiscoCE500InventoryCollector,
    CiscoIOSInventoryCollector,
    build_cisco_inventory_registry,
)
from backend.app.collectors.context import CollectorContext
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryTarget
from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
)
from backend.app.transports.manager import TransportManager
from backend.app.transports.session import TransportSession


@dataclass(slots=True, kw_only=True)
class FakeCommandSession(TransportSession):
    commands: dict[str, str]
    executed: list[str]

    async def close(self) -> None:
        self.mark_closed()

    async def execute(self, command: str) -> str:
        self.executed.append(command)
        return self.commands.get(command, "")


class FakeSSHTransport(BaseTransport):
    name = "netmiko"
    capabilities = frozenset({TransportCapability.SSH})

    def __init__(self, session: FakeCommandSession) -> None:
        self.session = session

    def health_check(self, context: TransportContext) -> None:
        return None

    def create_session(self, context: TransportContext) -> TransportSession:
        return self.session

    def close(self) -> None:
        return None


class FakeHTTPTransport(BaseTransport):
    name = "httpx"
    capabilities = frozenset({TransportCapability.HTTP})

    def health_check(self, context: TransportContext) -> None:
        return None

    def create_session(self, context: TransportContext) -> TransportSession:
        raise AssertionError("HTTP should not be selected when SSH is registered.")

    def close(self) -> None:
        return None


def test_factory_registers_supported_cisco_inventory_collectors() -> None:
    registry = build_cisco_inventory_registry(TransportManager())

    assert set(registry.names()) == {
        "cisco-catalyst-2960-inventory",
        "cisco-catalyst-2960x-inventory",
        "cisco-catalyst-3560-inventory",
        "cisco-ce500-inventory",
        "cisco-aironet-inventory",
    }
    assert registry.select(frozenset({CollectorCapability.INTERFACES}))


@pytest.mark.anyio
async def test_ios_collector_selects_ssh_before_http_and_collects_inventory() -> None:
    session = FakeCommandSession(
        session_id="switch-1",
        commands={
            "show version": "Switch uptime is 1 day",
            "show inventory": (
                'NAME: "1", DESCR: "x"\n'
                "PID: WS-C2960X-48FPS-L , VID: V05 , SN: FOC123"
            ),
        },
        executed=[],
    )
    manager = TransportManager()
    manager.register(FakeHTTPTransport())
    manager.register(FakeSSHTransport(session))
    collector = CiscoIOSInventoryCollector(
        transport_manager=manager,
        platform_family="catalyst-2960x",
    )
    context = CollectorContext(
        target=DiscoveryTarget(identifier="switch-1", address="10.0.0.10"),
    )

    payload = await collector.collect(context, discovered_targets=())

    assert payload["transport"] == "netmiko"
    assert payload["transport_capability"] == "SSH"
    assert "show running-config" not in session.executed
    assert "show startup-config" not in session.executed
    assert "show version" in session.executed


@pytest.mark.anyio
async def test_collector_normalize_produces_canonical_snapshot() -> None:
    manager = TransportManager()
    collector = CiscoCE500InventoryCollector(transport_manager=manager)
    context = CollectorContext(
        target=DiscoveryTarget(identifier="ce500-1", address="http://10.0.0.20"),
    )
    raw_payload = {
        "target": {
            "identifier": "ce500-1",
            "address": "http://10.0.0.20",
            "metadata": {"hostname": "ce500-1"},
        },
        "platform_family": "catalyst-express-500",
        "parser_family": "ce500",
        "transport": "httpx",
        "transport_capability": "HTTP",
        "http": {
            "/": "model: WS-CE500-24TT\nserial: CE123\nversion: 12.2",
            "/status": "base mac: 00:aa:bb:cc:dd:ee",
        },
    }

    snapshot = await collector.normalize(context, raw_payload, discovered_targets=())

    assert snapshot.devices[0].device_id == "ce500-1"
    assert snapshot.devices[0].model == "WS-CE500-24TT"
    assert snapshot.devices[0].serial_number == "CE123"
