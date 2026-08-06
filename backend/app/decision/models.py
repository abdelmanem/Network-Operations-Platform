"""Immutable decision artifacts for policy evaluation outcomes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.evaluation.context import EvaluationStatus


class DecisionStatus(StrEnum):
    """Supported decision states."""

    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    WARNING = "warning"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class DecisionRuleDefinition(BaseModel):
    """Rule definition used by the decision registry."""

    code: str
    description: str
    status: DecisionStatus
    confidence: int
    match_policy_statuses: tuple[EvaluationStatus, ...] = Field(default_factory=tuple)
    match_rule_statuses: tuple[EvaluationStatus, ...] = Field(default_factory=tuple)
    priority: int = 0

    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionReason(BaseModel):
    """Rationale for a decision status."""

    code: str
    message: str
    details: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionRule(BaseModel):
    """Decision summary for an evaluated rule."""

    rule_id: UUID
    rule_key: str
    status: EvaluationStatus
    risk_score: int
    confidence: int
    reason: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionTrace(BaseModel):
    """Trace of reasons and applied decision rules."""

    reasons: tuple[DecisionReason, ...] = Field(default_factory=tuple)
    rules: tuple[DecisionRule, ...] = Field(default_factory=tuple)

    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionRecord(BaseModel):
    """Immutable output record describing the final decision."""

    policy_id: UUID
    policy_version: str
    evaluation_id: UUID
    evaluation_timestamp: datetime
    decision_timestamp: datetime
    decision_status: DecisionStatus
    confidence: int
    reasoning: str
    triggered_rules: tuple[str, ...] = Field(default_factory=tuple)
    evaluator_version: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionResult(DecisionRecord):
    """Decision output with trace metadata."""

    trace: DecisionTrace = Field(default_factory=DecisionTrace)

    model_config = ConfigDict(extra="forbid", frozen=True)
