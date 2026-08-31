"""Tests for the concrete SSH transport adapters."""

# ruff: noqa: S105

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from backend.app.transports import (
    NetmikoSSHTransport,
    ParamikoSSHTransport,
    TransportContext,
    TransportRetryPolicy,
    TransportTarget,
)
from backend.app.transports.credentials import UsernamePasswordCredentials

SSH_PASSWORD = "secret"


@dataclass
class _FakeStdout:
    payload: str = "ok"

    def read(self) -> bytes:
        return self.payload.encode("utf-8")

    @property
    def channel(self) -> object:
        class _Channel:
            def recv_exit_status(self) -> int:
                return 0

        return _Channel()


@dataclass
class _FakeStderr:
    payload: str = ""

    def read(self) -> bytes:
        return self.payload.encode("utf-8")


class _FakeParamikoClient:
    def __init__(self) -> None:
        self.connected = False
        self.connect_attempts = 0
        self.exec_calls: list[str] = []

    def set_missing_host_key_policy(self, policy: object) -> None:
        return None

    def connect(self, **kwargs: object) -> None:
        self.connect_attempts += 1
        if self.connect_attempts < 2:
            raise ConnectionError("temporary failure")
        self.connected = True

    def exec_command(self, command: str) -> tuple[object, _FakeStdout, _FakeStderr]:
        self.exec_calls.append(command)
        return object(), _FakeStdout(), _FakeStderr()

    def close(self) -> None:
        self.connected = False


class _FakeNetmikoConnection:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def send_command(self, command: str) -> str:
        self.commands.append(command)
        return "ok"

    def disconnect(self) -> None:
        return None


def test_paramiko_transport_creates_authenticated_session(monkeypatch: object) -> None:
    fake_client = _FakeParamikoClient()

    monkeypatch.setattr(
        "backend.app.transports.ssh.paramiko._paramiko_module",
        lambda: SimpleNamespace(
            SSHClient=lambda: fake_client,
            AutoAddPolicy=lambda: object(),
            RejectPolicy=lambda: object(),
        ),
    )

    transport = ParamikoSSHTransport()
    context = TransportContext(
        target=TransportTarget(identifier="switch-1", address="10.0.0.1"),
        credentials=UsernamePasswordCredentials(
            username="admin", password=SSH_PASSWORD
        ),
        retry_policy=TransportRetryPolicy(max_attempts=2),
    )

    session = transport.create_session(context)

    async def run() -> None:
        await session.open()
        output = await session.execute("show version")
        await session.close()
        assert output == ("ok", "", 0)

    asyncio.run(run())
    assert fake_client.connected is False
    assert fake_client.connect_attempts == 2


def test_paramiko_transport_allows_unknown_host_keys_for_discovery(
    monkeypatch: object,
) -> None:
    policy_seen: list[str] = []

    class _FakeParamikoClient:
        def set_missing_host_key_policy(self, policy: object) -> None:
            policy_seen.append(type(policy).__name__)

        def connect(self, **kwargs: object) -> None:
            return None

        def exec_command(self, command: str) -> tuple[object, _FakeStdout, _FakeStderr]:
            return object(), _FakeStdout(), _FakeStderr()

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "backend.app.transports.ssh.paramiko._paramiko_module",
        lambda: SimpleNamespace(
            SSHClient=lambda: _FakeParamikoClient(),
            AutoAddPolicy=lambda: object(),
            RejectPolicy=lambda: object(),
        ),
    )

    transport = ParamikoSSHTransport()
    context = TransportContext(
        target=TransportTarget(identifier="switch-3", address="10.0.0.3"),
        credentials=UsernamePasswordCredentials(
            username="admin", password=SSH_PASSWORD
        ),
        retry_policy=TransportRetryPolicy(max_attempts=1),
    )

    session = transport.create_session(context)

    async def run() -> None:
        await session.open()
        await session.execute("show version")
        await session.close()

    asyncio.run(run())
    assert policy_seen == ["object"]


def test_netmiko_transport_creates_session(monkeypatch: object) -> None:
    fake_connection = _FakeNetmikoConnection()

    monkeypatch.setattr(
        "backend.app.transports.ssh.netmiko._netmiko_module",
        lambda: SimpleNamespace(ConnectHandler=lambda **kwargs: fake_connection),
    )

    transport = NetmikoSSHTransport()
    context = TransportContext(
        target=TransportTarget(identifier="switch-2", address="10.0.0.2"),
        credentials=UsernamePasswordCredentials(
            username="admin", password=SSH_PASSWORD
        ),
    )

    session = transport.create_session(context)

    async def run() -> None:
        await session.open()
        response = await session.execute("show version")
        await session.close()
        assert response == "ok"

    asyncio.run(run())
    assert fake_connection.commands == ["show version"]
