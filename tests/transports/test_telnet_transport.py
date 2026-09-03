"""Focused tests for explicit Telnet discovery and authentication."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest
from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.discovery.context import DiscoveryContext, DiscoveryTarget
from backend.app.discovery.contracts import DiscoveryFailureCode
from backend.app.discovery.multi_transport import MultiTransportDiscoveryOrchestrator
from backend.app.transports import (
    TelnetTransport,
    TransportCapability,
    TransportContext,
    TransportManager,
    TransportTarget,
    UsernamePasswordCredentials,
)
from backend.app.transports.credentials import (
    CredentialReference,
    CredentialResolutionError,
    ProfileSecretCredentialProvider,
)
from backend.app.transports.exceptions import (
    TransportAuthenticationError,
    TransportUnavailableError,
)
from backend.app.transports.telnet import telnetlib as telnet_transport


@dataclass(slots=True)
class Profile:
    id: object
    tenant_id: str
    provider_reference: str
    transport_types: list[str]
    credential_type: str
    username: str
    enabled: bool = True


class ContextProbeCollector(BaseCollector):
    def __init__(self) -> None:
        super().__init__(
            name="context-probe",
            capabilities=frozenset({TransportCapability.TELNET}),
        )

    async def health_check(self, context: CollectorContext) -> None:
        return None

    async def discover(self, context: CollectorContext) -> tuple[DiscoveryTarget, ...]:
        return ()

    async def collect(
        self,
        context: CollectorContext,
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> dict[str, object]:
        return {"transport": context.metadata["transport_name"]}

    async def normalize(
        self,
        context: CollectorContext,
        raw_payload: dict[str, object],
        *,
        discovered_targets: tuple[DiscoveryTarget, ...],
    ) -> object:
        raise AssertionError("Not used")

    async def close(self) -> None:
        return None


class FakeTelnetConnection:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = iter(responses)
        self.writes: list[bytes] = []
        self.opened = False
        self.closed = False

    def open(self, hostname: str, port: int, timeout: float | None) -> None:
        assert hostname == "10.0.0.1"
        assert port == 23
        self.opened = True

    def read_until(self, expected: bytes, timeout: float | None) -> bytes:
        return next(self.responses)

    def write(self, value: bytes) -> None:
        self.writes.append(value)

    def close(self) -> None:
        self.closed = True


def test_target_transport_is_propagated_to_collector_context() -> None:
    target = DiscoveryTarget(
        identifier="switch-1",
        address="10.0.0.1",
        tenant_id="tenant-a",
        metadata={"transport_name": "telnet"},
    )
    discovery_context = DiscoveryContext(
        target=target,
        required_capabilities=frozenset({TransportCapability.TELNET}),
    )

    context = ContextProbeCollector().build_context(discovery_context)

    assert context.metadata["transport_name"] == "telnet"


def test_telnet_profile_resolution_is_ephemeral_and_uses_provider_reference() -> None:
    profile = Profile(
        id=uuid4(),
        tenant_id="tenant-a",
        provider_reference="credential/cisco-telnet",
        transport_types=["telnet"],
        credential_type="telnet_password",
        username="admin",
    )
    calls: list[str] = []

    class SecretProvider:
        def resolve_secret(self, reference: str) -> str:
            calls.append(reference)
            return "runtime-secret"

    provider = ProfileSecretCredentialProvider(
        SecretProvider(), lambda _tenant, _profile_id: profile
    )
    credentials = provider.resolve_reference(
        CredentialReference(profile.id, "telnet", profile.tenant_id)
    )

    assert credentials == UsernamePasswordCredentials("admin", "runtime-secret")
    assert calls == ["credential/cisco-telnet"]


def test_telnet_session_exchanges_prompts_without_logging_password(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeTelnetConnection(
        [b"Username:", b"Password:", b"Switch#", b"show version\r\nSwitch#"]
    )
    monkeypatch.setattr(
        telnet_transport,
        "_telnetlib_module",
        lambda: SimpleNamespace(Telnet=lambda: fake),
    )
    transport = TelnetTransport()
    session = transport.create_session(
        TransportContext(
            target=TransportTarget("switch-1", "10.0.0.1"),
            credentials=UsernamePasswordCredentials("admin", "runtime-secret"),
        )
    )

    async def run() -> str:
        await session.open()
        output = await session.execute("show version")
        await session.close()
        return output

    assert asyncio.run(run()) == "show version\r\nSwitch#"
    assert fake.writes == [b"admin\n", b"runtime-secret\n", b"show version\n"]
    assert "runtime-secret" not in caplog.text


def test_telnet_authentication_rejection_is_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeTelnetConnection([b"Username:", b"Password:", b"Authentication failed"])
    monkeypatch.setattr(
        telnet_transport,
        "_telnetlib_module",
        lambda: SimpleNamespace(Telnet=lambda: fake),
    )
    session = TelnetTransport().create_session(
        TransportContext(
            target=TransportTarget("switch-1", "10.0.0.1"),
            credentials=UsernamePasswordCredentials("admin", "wrong"),
        )
    )

    with pytest.raises(TransportAuthenticationError):
        asyncio.run(session.open())


def test_missing_telnet_registration_is_transport_unavailable() -> None:
    with pytest.raises(TransportUnavailableError):
        TransportManager().resolve("telnet")

    orchestrator = MultiTransportDiscoveryOrchestrator()
    assert (
        orchestrator._classify_exception(TransportUnavailableError("telnet"))
        == DiscoveryFailureCode.TRANSPORT_UNAVAILABLE
    )
    assert (
        orchestrator._classify_exception(
            CredentialResolutionError("profile validation failed")
        )
        == DiscoveryFailureCode.CREDENTIAL_RESOLUTION_FAILED
    )
