"""Concrete SSH transport implementation built on Netmiko."""

# ruff: noqa: ANN401

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.app.transports._support import (
    extract_username_password,
    import_optional,
    metadata_int,
    metadata_optional_string,
    metadata_string,
    retry_async,
)
from backend.app.transports.base import TransportContext
from backend.app.transports.exceptions import TransportHealthCheckError
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.session import TransportSession
from backend.app.transports.ssh.base import SSHTransport
from backend.app.transports.ssh.session import SSHSession

logger = logging.getLogger(__name__)


def _netmiko_module() -> Any:
    return import_optional("netmiko", "netmiko")


@dataclass(slots=True, kw_only=True)
class NetmikoSSHSession(SSHSession):
    """Manage a Netmiko connection session."""

    hostname: str
    device_type: str
    port: int = 22
    username: str | None = None
    password: str | None = None
    secret: str | None = None
    timeout_seconds: float | None = None
    retry_policy: TransportRetryPolicy | None = None
    connection: Any | None = field(default=None, init=False, repr=False)

    async def open(self) -> None:
        """Open the SSH session."""

        if self.is_open:
            return

        netmiko = _netmiko_module()
        connect_kwargs: dict[str, Any] = {
            "device_type": self.device_type,
            "host": self.hostname,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "secret": self.secret,
            "timeout": self.timeout_seconds,
        }
        connect_kwargs = {
            key: value for key, value in connect_kwargs.items() if value is not None
        }

        async def operation() -> None:
            self.connection = await asyncio.to_thread(
                netmiko.ConnectHandler, **connect_kwargs
            )

        await retry_async(self.retry_policy, operation)
        await TransportSession.open(self)

    async def close(self) -> None:
        """Close the SSH session."""

        if self.connection is not None:
            await asyncio.to_thread(self.connection.disconnect)
            self.connection = None
        if self.closed_at is None:
            self.mark_closed()

    async def execute(self, command: str) -> str:
        """Execute a CLI command."""

        self.ensure_open()
        if self.connection is None:
            raise RuntimeError("Netmiko connection is not available.")

        return await asyncio.to_thread(self.connection.send_command, command)


@dataclass(slots=True)
class NetmikoSSHTransport(SSHTransport):
    """Concrete SSH transport backed by Netmiko."""

    name: str = "netmiko"
    default_device_type: str = "autodetect"
    default_port: int = 22
    session_kwargs: dict[str, object] = field(default_factory=dict)

    def health_check(self, context: TransportContext) -> None:
        """Validate SSH transport configuration."""

        if not context.target.address:
            raise TransportHealthCheckError("SSH target address is required.")

    def create_session(self, context: TransportContext) -> NetmikoSSHSession:
        """Create a Netmiko SSH session."""

        username, password = extract_username_password(context.credentials)
        port = metadata_int(context.metadata, "port", self.default_port)
        device_type = metadata_string(
            context.metadata,
            "device_type",
            self.default_device_type,
        )
        secret = metadata_optional_string(context.metadata, "secret")
        session = NetmikoSSHSession(
            session_id=context.target.identifier,
            hostname=context.target.address,
            device_type=device_type,
            port=port,
            username=username,
            password=password,
            secret=secret,
            timeout_seconds=(
                context.timeout.connect_seconds if context.timeout else None
            ),
            retry_policy=context.retry_policy,
        )
        logger.debug(
            "Prepared Netmiko session",
            extra={
                "target": context.target.identifier,
                "hostname": context.target.address,
            },
        )
        return session

    def close(self) -> None:
        """Release transport-level resources."""
