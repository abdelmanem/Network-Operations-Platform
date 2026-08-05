"""Transport diagnostics models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class TransportDiagnostic:
    """Describe transport connection state for troubleshooting."""

    transport_name: str
    target_identifier: str
    target_address: str
    connected: bool
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    detail: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a serializable diagnostic mapping."""

        return {
            "transport_name": self.transport_name,
            "target_identifier": self.target_identifier,
            "target_address": self.target_address,
            "connected": self.connected,
            "checked_at": self.checked_at.isoformat(),
            "detail": self.detail,
        }
