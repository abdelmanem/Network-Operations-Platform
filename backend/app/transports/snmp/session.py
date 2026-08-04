"""SNMP session abstraction."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.transports.session import TransportSession


@dataclass(slots=True)
class SNMPSession(TransportSession):
    """Abstract SNMP session base class."""

    async def close(self) -> None:
        self.mark_closed()
