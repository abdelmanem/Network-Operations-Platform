"""Evaluation context and decision models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID, uuid4

from backend.app.comparison.diff import Difference
from backend.app.comparison.result import InventoryComparisonResult
from backend.app.compliance.findings.evidence import Evidence
from backend.app.compliance.findings.models import Recommendation
from backend.app.compliance.findings.severity import Severity


class RuleType(StrEnum):
    """Supported executable rule types."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    EXISTS = "exists"
    MISSING = "missing"
    REGEX = "regex"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    VERSION_COMPARE = "version_compare"
    BOOLEAN_COMPARE = "boolean_compare"


class EvaluationStatus(StrEnum):
    """Compliance evaluation status values."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    WAIVED = "waived"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class EvaluationException:
    """Temporary exception or approved waiver for evaluation."""

    key: str
    reason: str
    approved_by: str
    subject_type: str | None = None
    subject_id: str | None = None
    rule_key: str | None = None
    expires_at: datetime | None = None
    approved_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def applies_to(self, rule_key: str, difference: Difference) -> bool:
        """Return whether this exception waives a rule/difference pair."""

        if self.expires_at is not None and self.expires_at <= datetime.now(UTC):
            return False
        if self.rule_key is not None and self.rule_key != rule_key:
            return False
        if (
            self.subject_type is not None
            and self.subject_type != difference.subject_type
        ):
            return False
        if self.subject_id is not None and self.subject_id != difference.subject_id:
            return False
        return True


@dataclass(frozen=True, slots=True)
class RuleEvaluationResult:
    """Immutable result for one rule against one difference."""

    rule_id: UUID
    rule_key: str
    difference: Difference
    status: EvaluationStatus
    passed: bool
    risk_score: int
    severity: Severity
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    recommendation: Recommendation | None = None
    exception: EvaluationException | None = None
    message: str | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class PolicyEvaluationResult:
    """Immutable per-policy compliance evaluation result."""

    policy_id: UUID
    policy_key: str
    version: str
    status: EvaluationStatus
    risk_score: int
    compliance_score: int
    rule_results: tuple[RuleEvaluationResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    """Evaluation metrics snapshot."""

    total_rules: int
    evaluated_rules: int
    compliant: int
    non_compliant: int
    waived: int
    not_applicable: int
    errors: int
    risk_score: int
    compliance_score: int


@dataclass(frozen=True, slots=True)
class EvaluationDecision:
    """Immutable final compliance decision."""

    id: UUID = field(default_factory=uuid4)
    status: EvaluationStatus = EvaluationStatus.NOT_APPLICABLE
    risk_score: int = 0
    compliance_score: int = 100
    severity: Severity | None = None
    recommendations: tuple[Recommendation, ...] = field(default_factory=tuple)
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    rule_results: tuple[RuleEvaluationResult, ...] = field(default_factory=tuple)
    policy_results: tuple[PolicyEvaluationResult, ...] = field(default_factory=tuple)
    metrics: EvaluationMetrics | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Inputs used during compliance evaluation."""

    comparison_result: InventoryComparisonResult
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))
    exceptions: tuple[EvaluationException, ...] = field(default_factory=tuple)

    @property
    def site(self) -> str | None:
        """Return optional site scope."""

        return self._text("site")

    @property
    def device_role(self) -> str | None:
        """Return optional device role scope."""

        return self._text("device_role")

    @property
    def platform(self) -> str | None:
        """Return optional platform scope."""

        return self._text("platform")

    @property
    def vendor(self) -> str | None:
        """Return optional vendor scope."""

        return self._text("vendor")

    @property
    def device_type(self) -> str | None:
        """Return optional device type scope."""

        return self._text("device_type")

    def _text(self, key: str) -> str | None:
        value = self.metadata.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None
