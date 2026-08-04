"""HTTP session abstraction."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.transports.session import TransportSession


@dataclass(slots=True)
class HTTPSession(TransportSession):
    """Abstract HTTP session base class."""

    async def close(self) -> None:
        self.mark_closed()
