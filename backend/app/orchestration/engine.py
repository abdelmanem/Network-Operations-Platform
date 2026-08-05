"""Top-level orchestration engine."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.orchestration.context import OrchestrationContext
from backend.app.orchestration.jobs import OrchestrationJob
from backend.app.orchestration.results import OrchestrationResult
from backend.app.orchestration.workflow import WorkflowEngine


@dataclass(slots=True)
class OrchestrationEngine:
    """Create and execute orchestration jobs."""

    workflow: WorkflowEngine

    async def run(
        self,
        context: OrchestrationContext,
        *,
        priority: int = 0,
    ) -> OrchestrationResult:
        """Execute one context immediately."""

        job = OrchestrationJob(context=context, priority=priority)
        return await self.workflow.execute(job)
