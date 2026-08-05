"""Rule execution for compliance evaluation."""

from __future__ import annotations

import operator
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from backend.app.comparison.diff import Difference
from backend.app.compliance.findings.evidence import Evidence
from backend.app.compliance.rules.base import Rule
from backend.app.evaluation.context import (
    EvaluationException,
    EvaluationStatus,
    RuleEvaluationResult,
    RuleType,
)
from backend.app.evaluation.exceptions import RuleEvaluationError
from backend.app.evaluation.remediation import RecommendationBuilder
from backend.app.evaluation.scoring import RiskCalculator


@dataclass(slots=True)
class RuleExecutor:
    """Execute typed rules against comparison differences."""

    risk_calculator: RiskCalculator
    recommendation_builder: RecommendationBuilder

    def execute(
        self,
        rule: Rule,
        difference: Difference,
        *,
        exception: EvaluationException | None = None,
    ) -> RuleEvaluationResult:
        """Evaluate a rule against one difference."""

        rule_type = self._rule_type(rule)
        if exception is not None:
            return self._waived(rule, difference, exception)

        passed = self._evaluate(rule_type, rule.expected_state, difference)
        status = (
            EvaluationStatus.COMPLIANT if passed else EvaluationStatus.NON_COMPLIANT
        )
        risk_score = 0 if passed else self.risk_calculator.score(rule, difference)
        severity = self.risk_calculator.severity_for_score(risk_score)
        recommendation = (
            None
            if passed
            else self.recommendation_builder.build(
                rule,
                difference,
                severity,
            )
        )
        return RuleEvaluationResult(
            rule_id=rule.id,
            rule_key=rule.key,
            difference=difference,
            status=status,
            passed=passed,
            risk_score=risk_score,
            severity=severity,
            evidence=(self._evidence(rule, difference, passed),),
            recommendation=recommendation,
            message="Rule passed." if passed else "Rule failed.",
        )

    def _waived(
        self,
        rule: Rule,
        difference: Difference,
        exception: EvaluationException,
    ) -> RuleEvaluationResult:
        severity = self.risk_calculator.severity_for_score(0)
        return RuleEvaluationResult(
            rule_id=rule.id,
            rule_key=rule.key,
            difference=difference,
            status=EvaluationStatus.WAIVED,
            passed=True,
            risk_score=0,
            severity=severity,
            evidence=(self._evidence(rule, difference, True),),
            recommendation=None,
            exception=exception,
            message=f"Rule waived by {exception.approved_by}: {exception.reason}",
        )

    def _evaluate(
        self,
        rule_type: RuleType,
        expected_state: Mapping[str, object],
        difference: Difference,
    ) -> bool:
        expected = expected_state.get("expected", difference.expected)
        observed = difference.observed
        handlers: dict[RuleType, Callable[[object | None, object | None], bool]] = {
            RuleType.EQUALS: lambda exp, obs: self._normalize(exp)
            == self._normalize(obs),
            RuleType.NOT_EQUALS: lambda exp, obs: self._normalize(exp)
            != self._normalize(obs),
            RuleType.EXISTS: lambda exp, obs: obs is not None
            and str(obs).strip() != "",
            RuleType.MISSING: lambda exp, obs: obs is None or str(obs).strip() == "",
            RuleType.REGEX: self._regex,
            RuleType.CONTAINS: lambda exp, obs: str(exp) in str(obs),
            RuleType.GREATER_THAN: self._compare(operator.gt),
            RuleType.LESS_THAN: self._compare(operator.lt),
            RuleType.VERSION_COMPARE: self._version_compare,
            RuleType.BOOLEAN_COMPARE: lambda exp, obs: self._bool(exp)
            == self._bool(obs),
        }
        try:
            return handlers[rule_type](expected, observed)
        except Exception as exc:
            raise RuleEvaluationError(
                f"Rule {rule_type.value!r} failed to evaluate."
            ) from exc

    @staticmethod
    def _rule_type(rule: Rule) -> RuleType:
        value = rule.expected_state.get("rule_type", RuleType.EQUALS.value)
        try:
            return RuleType(str(value))
        except ValueError as exc:
            raise RuleEvaluationError(f"Unsupported rule type: {value!r}") from exc

    @staticmethod
    def _normalize(value: object | None) -> str:
        return "" if value is None else str(value).strip().casefold()

    @staticmethod
    def _regex(expected: object | None, observed: object | None) -> bool:
        if expected is None or observed is None:
            return False
        return re.search(str(expected), str(observed)) is not None

    @staticmethod
    def _compare(
        operation: Callable[[float, float], bool]
    ) -> Callable[[object | None, object | None], bool]:
        def compare(expected: object | None, observed: object | None) -> bool:
            if expected is None or observed is None:
                return False
            return operation(float(str(observed)), float(str(expected)))

        return compare

    @staticmethod
    def _version_compare(expected: object | None, observed: object | None) -> bool:
        if expected is None or observed is None:
            return False
        return RuleExecutor._version_tuple(observed) >= RuleExecutor._version_tuple(
            expected
        )

    @staticmethod
    def _version_tuple(value: object) -> tuple[int, ...]:
        parts = re.findall(r"\d+", str(value))
        return tuple(int(part) for part in parts)

    @staticmethod
    def _bool(value: object | None) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().casefold()
        if normalized in {"true", "yes", "enabled", "up", "1"}:
            return True
        if normalized in {"false", "no", "disabled", "down", "0"}:
            return False
        return None

    @staticmethod
    def _evidence(rule: Rule, difference: Difference, passed: bool) -> Evidence:
        return Evidence.create(
            "evaluation-engine",
            f"Rule {rule.key} {'passed' if passed else 'failed'} for {difference.key}.",
            reference=f"evaluation:{rule.key}:{difference.key}",
            details={
                "rule_id": str(rule.id),
                "rule_key": rule.key,
                "difference_id": str(difference.id),
                "difference_key": difference.key,
                "expected": difference.expected,
                "observed": difference.observed,
                "passed": passed,
            },
        )


def stable_rule_id(key: str) -> UUID:
    """Return a stable UUID for generated evaluation rules."""

    return uuid5(NAMESPACE_URL, f"nop-evaluation:{key}")
