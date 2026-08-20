"""Concrete SNMP transport implementation built on pysnmp."""

# ruff: noqa: ANN401

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.app.transports._support import (
    import_optional,
    metadata_int,
    metadata_optional_string,
    retry_async,
)
from backend.app.transports.base import TransportContext
from backend.app.transports.credentials import SNMPv2cCredentials
from backend.app.transports.exceptions import (
    TransportConfigurationError,
    TransportHealthCheckError,
)
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.session import TransportSession
from backend.app.transports.snmp.base import SNMPTransport
from backend.app.transports.snmp.session import SNMPSession

logger = logging.getLogger(__name__)


def _pysnmp_asyncio() -> Any:
    return import_optional("pysnmp.hlapi.asyncio", "pysnmp")


@dataclass(slots=True, kw_only=True)
class PySnmpSession(SNMPSession):
    """Manage a pysnmp session."""

    hostname: str
    port: int = 161
    community: str = "public"
    timeout_seconds: float | None = None
    retries: int = 1
    retry_policy: TransportRetryPolicy | None = None
    engine: Any | None = field(default=None, init=False, repr=False)

    async def open(self) -> None:
        """Open the SNMP session."""

        if self.is_open:
            return

        pysnmp = _pysnmp_asyncio()

        async def operation() -> None:
            self.engine = pysnmp.SnmpEngine()

        await retry_async(self.retry_policy, operation)
        await TransportSession.open(self)

    async def close(self) -> None:
        """Close the SNMP session."""

        self.engine = None
        if self.closed_at is None:
            self.mark_closed()

    async def get(self, oid: str) -> tuple[str, Any]:
        """Perform a generic SNMP GET."""

        self.ensure_open()
        if self.engine is None:
            raise RuntimeError("SNMP engine is not available.")

        async def operation() -> tuple[str, Any]:
            pysnmp = _pysnmp_asyncio()
            (
                error_indication,
                error_status,
                error_index,
                var_binds,
            ) = await pysnmp.get_cmd(
                self.engine,
                pysnmp.CommunityData(self.community),
                pysnmp.UdpTransportTarget(
                    (self.hostname, self.port),
                    timeout=self.timeout_seconds,
                    retries=self.retries,
                ),
                pysnmp.ContextData(),
                pysnmp.ObjectType(pysnmp.ObjectIdentity(oid)),
            )
            if error_indication:
                raise RuntimeError(str(error_indication))
            if error_status:
                raise RuntimeError(f"{error_status.prettyPrint()} at {error_index}")
            return oid, var_binds[0][1]

        return await retry_async(self.retry_policy, operation)

    async def walk(self, oid: str) -> list[tuple[str, Any]]:
        """Perform a generic SNMP walk."""

        self.ensure_open()
        if self.engine is None:
            raise RuntimeError("SNMP engine is not available.")

        async def operation() -> list[tuple[str, Any]]:
            pysnmp = _pysnmp_asyncio()
            results: list[tuple[str, Any]] = []
            (
                error_indication,
                error_status,
                error_index,
                var_bind_table,
            ) = await pysnmp.next_cmd(
                self.engine,
                pysnmp.CommunityData(self.community),
                pysnmp.UdpTransportTarget(
                    (self.hostname, self.port),
                    timeout=self.timeout_seconds,
                    retries=self.retries,
                ),
                pysnmp.ContextData(),
                pysnmp.ObjectType(pysnmp.ObjectIdentity(oid)),
                lexicographic_mode=False,
            )
            if error_indication:
                raise RuntimeError(str(error_indication))
            if error_status:
                raise RuntimeError(f"{error_status.prettyPrint()} at {error_index}")
            for row in var_bind_table:
                for name, value in row:
                    results.append((str(name), value))
            return results

        return await retry_async(self.retry_policy, operation)


@dataclass(slots=True)
class PySnmpTransport(SNMPTransport):
    """Concrete SNMP transport backed by pysnmp."""

    name: str = "pysnmp"
    default_port: int = 161
    default_community: str = "public"
    retries: int = 1

    def health_check(self, context: TransportContext) -> None:
        """Validate SNMP transport configuration."""

        if not context.target.address:
            raise TransportHealthCheckError("SNMP target address is required.")
        if context.timeout is not None and context.timeout.connect_seconds is not None:
            if context.timeout.connect_seconds <= 0:
                raise TransportConfigurationError(
                    "SNMP connect timeout must be positive."
                )

    def create_session(self, context: TransportContext) -> PySnmpSession:
        """Create a pysnmp session."""

        community = None
        if isinstance(context.credentials, SNMPv2cCredentials):
            community = context.credentials.community
        if community is None:
            community = metadata_optional_string(context.metadata, "community")
        if community is None:
            community = self.default_community
        port = metadata_int(context.metadata, "port", self.default_port)
        session = PySnmpSession(
            session_id=context.target.identifier,
            hostname=context.target.address,
            port=port,
            community=community,
            timeout_seconds=(
                context.timeout.connect_seconds if context.timeout else None
            ),
            retries=self.retries,
            retry_policy=context.retry_policy,
        )
        logger.debug(
            "Prepared pysnmp session",
            extra={
                "target": context.target.identifier,
                "hostname": context.target.address,
            },
        )
        return session

    def close(self) -> None:
        """Release transport-level resources."""
