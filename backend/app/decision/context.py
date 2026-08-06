"""Decision context used to derive deterministic decision records."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from backend.app.evaluation.context import PolicyEvaluationResult


class DecisionContext(BaseModel):
    """Immutable decision input context."""

    evaluation_id: UUID = Field(default_factory=uuid4)
    evaluation_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decision_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    policy_results: tuple[PolicyEvaluationResult, ...] = Field(default_factory=tuple)
    evaluator_version: str = "1.0.0"

    model_config = ConfigDict(extra="forbid", frozen=True)
