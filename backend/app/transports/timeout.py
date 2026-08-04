"""Transport timeout management."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransportTimeout:
    """Represent configurable transport timeouts."""

    connect_seconds: float | None = 10.0
    read_seconds: float | None = 30.0
    write_seconds: float | None = 30.0
    total_seconds: float | None = None

    def as_dict(self) -> dict[str, float | None]:
        """Return a serializable timeout mapping."""

        return {
            "connect": self.connect_seconds,
            "read": self.read_seconds,
            "write": self.write_seconds,
            "total": self.total_seconds,
        }
