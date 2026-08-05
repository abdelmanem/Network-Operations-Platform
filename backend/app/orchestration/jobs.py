"""Orchestration job model."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from backend.app.orchestration.context import OrchestrationContext
from backend.app.orchestration.state import OrchestrationState


@dataclass(slots=True)
class OrchestrationJob:
    """One executable orchestration job."""

    context: OrchestrationContext
    id: UUID = field(default_factory=uuid4)
    state: OrchestrationState = field(default_factory=OrchestrationState)
    priority: int = 0

    def cancel(self, reason: str = "Run cancelled.") -> None:
        """Request cancellation for this job."""

        self.context.cancellation_token.cancel(reason)
        self.state.mark_cancelled(reason)
