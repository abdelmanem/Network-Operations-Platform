"""Cooperative job cancellation primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CancellationToken:
    """Cooperative cancellation token."""

    reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation was requested."""

        return self.reason is not None

    def cancel(self, reason: str = "Job cancelled.") -> None:
        """Request cancellation."""

        self.reason = reason
