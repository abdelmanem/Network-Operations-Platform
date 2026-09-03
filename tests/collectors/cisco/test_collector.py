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
from backend.app.discovery.contracts import DiscoveryTransportPolicy
from backend.app.discovery.transport_policy import MultiTransportPolicy
from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
)
from backend.app.transports.manager import TransportManager
from backend.app.transports.session import TransportSession
from backend.app.transports.telnet import TelnetTransport


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


class FakeTelnetTransport(TelnetTransport):
    """Registered Telnet transport used to verify explicit selector choice."""

    def __init__(self) -> None:
        super().__init__()


def test_catalyst_2960_advertises_ssh_snmp_and_telnet() -> None:
    from backend.app.vendors.cisco.models.ios import CATALYST_2960

    assert CATALYST_2960.metadata.transport_support == frozenset(
        {
            TransportCapability.SSH,
            TransportCapability.SNMP,
            TransportCapability.TELNET,
        }
    )


def test_catalyst_2960_explicit_telnet_selects_registered_telnet_transport() -> None:
    from backend.app.collectors.cisco.base import CiscoTransportSelector

    manager = TransportManager()
    manager.register(
        FakeSSHTransport(FakeCommandSession(session_id="ssh", commands={}, executed=[]))
    )
    manager.register(FakeTelnetTransport())
    selector = CiscoTransportSelector(manager)
    from backend.app.vendors.cisco.models.ios import CATALYST_2960

    selection = selector.select(CATALYST_2960, preferred_transport_name="telnet")

    assert selection.capability == TransportCapability.TELNET
    assert selection.transport_name == "telnet"
    assert manager.resolve(selection.transport_name).name == "telnet"


def test_telnet_policy_still_requires_explicit_insecure_opt_in() -> None:
    with pytest.raises(ValueError, match="Telnet"):
        DiscoveryTransportPolicy(
            preferred=TransportCapability.TELNET,
        ).ordered()

    policy = MultiTransportPolicy.from_credential_profile(
        type(
            "Profile",
            (),
            {
                "id": "profile-1",
                "transport_types": ["telnet"],
                "credential_type": "telnet_password",
            },
        )(),
        allow_insecure=True,
    )
    assert policy.transport_names == ["telnet"]


def test_factory_registers_supported_cisco_inventory_collectors() -> None:
    registry = build_cisco_inventory_registry(TransportManager())

    assert set(registry.names()) == {
        "cisco-catalyst-2960-inventory",
        "cisco-catalyst-2960x-inventory",
        "cisco-catalyst-3560-inventory",
        "cisco-ce500-inventory",
        "cisco-aironet-inventory",
        "cisco-ios-inventory",
    }
    ios_collector = registry.get("cisco-ios-inventory")
    platform_collector = registry.get("cisco-catalyst-2960x-inventory")
    assert ios_collector is platform_collector
    assert registry.select(frozenset({CollectorCapability.INTERFACES}))


def test_ios_collector_resolves_public_platform_hints_to_canonical_families() -> None:
    manager = TransportManager()
    collector = CiscoIOSInventoryCollector(transport_manager=manager)

    ios_context = CollectorContext(
        target=DiscoveryTarget(identifier="switch-ios", address="10.0.0.11"),
        metadata={"platform_family": "cisco-ios"},
    )
    iosxe_context = CollectorContext(
        target=DiscoveryTarget(identifier="switch-iosxe", address="10.0.0.12"),
        metadata={"platform_family": "cisco-iosxe"},
    )

    assert collector.resolve_platform(ios_context).metadata.family == "catalyst-2960"
    assert collector.resolve_platform(iosxe_context).metadata.family == "catalyst-2960x"


@pytest.mark.anyio
async def test_ios_collector_selects_ssh_before_http_and_collects_inventory() -> None:
    session = FakeCommandSession(
        session_id="switch-1",
        commands={
            "show version": "Switch uptime is 1 day",
            "show inventory": (
                'NAME: "1", DESCR: "x"\nPID: WS-C2960X-48FPS-L , VID: V05 , SN: FOC123'
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
