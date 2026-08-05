"""Orchestration run context."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.compliance.policies.models import Policy
from backend.app.evaluation.context import EvaluationException
from backend.app.events.interfaces import EventPublisher
from backend.app.orchestration.progress import OrchestrationProgress

ProgressCallback = Callable[[OrchestrationProgress], Awaitable[None] | None]


@dataclass(slots=True)
class CancellationToken:
    """Cooperative cancellation token."""

    reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation was requested."""

        return self.reason is not None

    def cancel(self, reason: str = "Run cancelled.") -> None:
        """Request cancellation."""

        self.reason = reason


@dataclass(frozen=True, slots=True)
class OrchestrationContext:
    """Dependency-free run context for end-to-end orchestration."""

    collector_contexts: tuple[CollectorRuntimeContext, ...]
    policies: tuple[Policy, ...] = field(default_factory=tuple)
    exceptions: tuple[EvaluationException, ...] = field(default_factory=tuple)
    metadata: dict[str, object] = field(default_factory=dict)
    run_id: UUID = field(default_factory=uuid4)
    max_attempts: int = 1
    retry_delay_seconds: float = 0.0
    force_netbox_refresh: bool = False
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)
    progress_callback: ProgressCallback | None = None
    event_publisher: EventPublisher | None = None
