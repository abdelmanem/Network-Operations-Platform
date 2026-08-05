from __future__ import annotations

from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.compliance.domain.enums import RuleStatus
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.evaluation import (
    EvaluationStatus,
    RecommendationBuilder,
    RiskCalculator,
    RuleExecutor,
    RuleType,
)


def _rule(rule_type: RuleType, *, expected: object = "expected") -> Rule:
    return Rule.create(
        f"rule-{rule_type.value}",
        f"Rule {rule_type.value}",
        RuleMetadata(version="1.0", status=RuleStatus.ACTIVE),
        expected_state={
            "rule_type": rule_type.value,
            "expected": expected,
            "risk_score": 60,
        },
    )


def _executor() -> RuleExecutor:
    return RuleExecutor(
        risk_calculator=RiskCalculator(),
        recommendation_builder=RecommendationBuilder(),
    )


def test_rule_executor_supports_core_rule_types() -> None:
    cases = (
        (_rule(RuleType.EQUALS), "expected", True),
        (_rule(RuleType.NOT_EQUALS), "other", True),
        (_rule(RuleType.EXISTS), "anything", True),
        (_rule(RuleType.MISSING), None, True),
        (_rule(RuleType.REGEX, expected=r"^IOS"), "IOS XE", True),
        (_rule(RuleType.CONTAINS, expected="XE"), "IOS XE", True),
        (_rule(RuleType.GREATER_THAN, expected=10), 20, True),
        (_rule(RuleType.LESS_THAN, expected=10), 5, True),
        (_rule(RuleType.VERSION_COMPARE, expected="15.2"), "15.2(7)E7", True),
        (_rule(RuleType.BOOLEAN_COMPARE, expected=True), "enabled", True),
    )

    for rule, observed, expected_result in cases:
        difference = Difference.create(
            DifferenceType.MODIFIED,
            "device",
            "switch-01",
            expected=rule.expected_state.get("expected"),
            observed=observed,
        )
        result = _executor().execute(rule, difference)

        assert result.passed is expected_result
        assert result.status == EvaluationStatus.COMPLIANT


def test_rule_executor_assigns_risk_and_recommendation_on_failure() -> None:
    rule = _rule(RuleType.EQUALS)
    difference = Difference.create(
        DifferenceType.MODIFIED,
        "device",
        "switch-01",
        field_name="serial",
        expected="ABC",
        observed="XYZ",
    )

    result = _executor().execute(rule, difference)

    assert result.status == EvaluationStatus.NON_COMPLIANT
    assert result.risk_score == 60
    assert result.recommendation is not None
    assert result.evidence
