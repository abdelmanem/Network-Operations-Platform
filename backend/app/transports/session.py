"""Transport session lifecycle helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class TransportSession(ABC):
    """Base class for reusable transport sessions."""

    session_id: str
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        """Return whether the session is open."""

        return self.opened_at is not None and self.closed_at is None

    async def __aenter__(self) -> TransportSession:
        await self.open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        await self.close()

    async def open(self) -> None:
        """Open the session."""

        if self.is_open:
            return

        self.opened_at = datetime.now(UTC)
        self.closed_at = None

    @abstractmethod
    async def close(self) -> None:
        """Close the session."""

    def mark_closed(self) -> None:
        """Record the closed timestamp."""

        self.closed_at = datetime.now(UTC)

    def ensure_open(self) -> None:
        """Ensure the session is open before use."""

        if not self.is_open:
            raise RuntimeError("Transport session is not open.")
