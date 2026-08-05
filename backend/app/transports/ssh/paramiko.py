"""Concrete SSH transport implementation built on Paramiko."""

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
    retry_async,
)
from backend.app.transports.base import TransportContext
from backend.app.transports.exceptions import (
    TransportConfigurationError,
    TransportHealthCheckError,
)
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.session import TransportSession
from backend.app.transports.ssh.base import SSHTransport
from backend.app.transports.ssh.session import SSHSession

logger = logging.getLogger(__name__)


def _paramiko_module() -> Any:
    return import_optional("paramiko", "paramiko")


@dataclass(slots=True, kw_only=True)
class ParamikoSSHSession(SSHSession):
    """Manage a Paramiko SSH client session."""

    hostname: str
    port: int = 22
    username: str | None = None
    password: str | None = None
    timeout_seconds: float | None = None
    allow_agent: bool = False
    look_for_keys: bool = False
    retry_policy: TransportRetryPolicy | None = None
    client: Any | None = field(default=None, init=False, repr=False)

    async def open(self) -> None:
        """Open the SSH session."""

        if self.is_open:
            return

        paramiko = _paramiko_module()
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client = self.client
        assert client is not None

        async def operation() -> None:
            await asyncio.to_thread(
                client.connect,
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout_seconds,
                allow_agent=self.allow_agent,
                look_for_keys=self.look_for_keys,
            )

        await retry_async(self.retry_policy, operation)
        await TransportSession.open(self)

    async def close(self) -> None:
        """Close the SSH session."""

        if self.client is not None:
            await asyncio.to_thread(self.client.close)
            self.client = None
        if self.closed_at is None:
            self.mark_closed()

    async def execute(self, command: str) -> tuple[str, str, int]:
        """Execute a shell command."""

        self.ensure_open()
        client = self.client
        if client is None:
            raise RuntimeError("SSH client is not available.")

        def operation() -> tuple[str, str, int]:
            stdin, stdout, stderr = client.exec_command(command)
            stdout_text = stdout.read().decode("utf-8", errors="ignore")
            stderr_text = stderr.read().decode("utf-8", errors="ignore")
            exit_status = stdout.channel.recv_exit_status()
            return stdout_text, stderr_text, exit_status

        return await asyncio.to_thread(operation)


@dataclass(slots=True)
class ParamikoSSHTransport(SSHTransport):
    """Concrete SSH transport backed by Paramiko."""

    name: str = "paramiko"
    default_port: int = 22
    allow_agent: bool = False
    look_for_keys: bool = False

    def health_check(self, context: TransportContext) -> None:
        """Validate SSH transport configuration."""

        if not context.target.address:
            raise TransportHealthCheckError("SSH target address is required.")
        if context.timeout is not None and context.timeout.connect_seconds is not None:
            if context.timeout.connect_seconds <= 0:
                raise TransportConfigurationError(
                    "SSH connect timeout must be positive."
                )

    def create_session(self, context: TransportContext) -> ParamikoSSHSession:
        """Create a Paramiko SSH session."""

        username, password = extract_username_password(context.credentials)
        port = metadata_int(context.metadata, "port", self.default_port)
        session = ParamikoSSHSession(
            session_id=context.target.identifier,
            hostname=context.target.address,
            port=port,
            username=username,
            password=password,
            timeout_seconds=(
                context.timeout.connect_seconds if context.timeout else None
            ),
            allow_agent=self.allow_agent,
            look_for_keys=self.look_for_keys,
            retry_policy=context.retry_policy,
        )
        logger.debug(
            "Prepared Paramiko session",
            extra={
                "target": context.target.identifier,
                "hostname": context.target.address,
            },
        )
        return session

    def close(self) -> None:
        """Release transport-level resources."""
