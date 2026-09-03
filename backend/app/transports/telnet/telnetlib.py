"""Concrete Telnet transport backed by Python's telnetlib."""

# ruff: noqa: ANN401

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, cast

from backend.app.transports._support import (
    extract_username_password,
    import_optional,
    metadata_int,
    retry_async,
)
from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
    TransportSecurity,
)
from backend.app.transports.exceptions import (
    TransportAuthenticationError,
    TransportConfigurationError,
    TransportConnectionError,
    TransportHealthCheckError,
)
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.session import TransportSession


def _telnetlib_module() -> Any:
    return import_optional("telnetlib", "telnetlib")


@dataclass(slots=True, kw_only=True)
class TelnetSession(TransportSession):
    """Manage an authenticated Telnet CLI session."""

    hostname: str
    port: int = 23
    username: str | None = None
    password: str | None = None
    timeout_seconds: float | None = None
    prompt: bytes = b"#"
    username_prompt: bytes = b"Username:"
    password_prompt: bytes = b"Password:"
    retry_policy: TransportRetryPolicy | None = None
    connection: Any | None = field(default=None, init=False, repr=False)

    async def open(self) -> None:
        """Open the socket and complete the Telnet login exchange."""

        if self.is_open:
            return
        if self.username is None or self.password is None:
            raise TransportConfigurationError(
                "Telnet username and password are required."
            )
        username = self.username
        password = self.password

        telnetlib = _telnetlib_module()

        async def operation() -> None:
            connection = telnetlib.Telnet()
            await asyncio.to_thread(
                connection.open,
                self.hostname,
                self.port,
                self.timeout_seconds,
            )
            try:
                username_response = await asyncio.to_thread(
                    connection.read_until,
                    self.username_prompt,
                    self.timeout_seconds,
                )
                if self.username_prompt not in username_response:
                    raise TransportConnectionError(
                        "Telnet username prompt was not received."
                    )
                await asyncio.to_thread(connection.write, username.encode() + b"\n")

                password_response = await asyncio.to_thread(
                    connection.read_until,
                    self.password_prompt,
                    self.timeout_seconds,
                )
                if self.password_prompt not in password_response:
                    raise TransportConnectionError(
                        "Telnet password prompt was not received."
                    )
                await asyncio.to_thread(connection.write, password.encode() + b"\n")

                login_response = await asyncio.to_thread(
                    connection.read_until,
                    self.prompt,
                    self.timeout_seconds,
                )
                lowered = login_response.lower()
                if any(
                    marker in lowered
                    for marker in (
                        b"authentication failed",
                        b"login invalid",
                        b"invalid password",
                        b"access denied",
                    )
                ):
                    raise TransportAuthenticationError(
                        "Telnet device rejected authentication."
                    )
                if self.prompt not in login_response:
                    raise TransportConnectionError(
                        "Telnet command prompt was not received after authentication."
                    )
            except Exception:
                await asyncio.to_thread(connection.close)
                raise
            self.connection = connection

        await retry_async(self.retry_policy, operation)
        await TransportSession.open(self)

    async def close(self) -> None:
        """Close the Telnet connection."""

        if self.connection is not None:
            await asyncio.to_thread(self.connection.close)
            self.connection = None
        if self.closed_at is None:
            self.mark_closed()

    async def execute(self, command: str) -> str:
        """Execute a CLI command and read through the device prompt."""

        self.ensure_open()
        if self.connection is None:
            raise RuntimeError("Telnet connection is not available.")
        await asyncio.to_thread(self.connection.write, command.encode() + b"\n")
        response = cast(
            bytes,
            await asyncio.to_thread(
                self.connection.read_until,
                self.prompt,
                self.timeout_seconds,
            ),
        )
        return response.decode("utf-8", errors="ignore")


@dataclass(slots=True)
class TelnetTransport(BaseTransport):
    """Concrete insecure transport backed by Python's telnetlib."""

    name: str = "telnet"
    capabilities: frozenset[TransportCapability] = frozenset(
        {TransportCapability.TELNET}
    )
    security: TransportSecurity = TransportSecurity.INSECURE

    def health_check(self, context: TransportContext) -> None:
        """Validate Telnet target configuration."""

        if not context.target.address:
            raise TransportHealthCheckError("Telnet target address is required.")

    def create_session(self, context: TransportContext) -> TelnetSession:
        """Create a Telnet session with ephemeral credentials."""

        username, password = extract_username_password(context.credentials)
        return TelnetSession(
            session_id=context.target.identifier,
            hostname=context.target.address,
            port=metadata_int(context.metadata, "port", 23),
            username=username,
            password=password,
            timeout_seconds=(
                context.timeout.connect_seconds if context.timeout else None
            ),
            retry_policy=context.retry_policy,
        )

    def close(self) -> None:
        """Release transport-level resources."""
