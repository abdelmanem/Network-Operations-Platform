from __future__ import annotations

import pytest
from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.compliance.domain.enums import RuleStatus
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.evaluation import (
    ComplianceScoreCalculator,
    EvaluationRuleRegistry,
    RiskCalculator,
)
from backend.app.evaluation.exceptions import RuleRegistrationError


def _rule() -> Rule:
    return Rule.create(
        "risk-rule",
        "Risk Rule",
        RuleMetadata(version="1.0", status=RuleStatus.ACTIVE),
        expected_state={"risk_score": 90},
    )


def test_risk_and_compliance_score_calculators() -> None:
    risk = RiskCalculator().score(
        _rule(),
        Difference.create(DifferenceType.MISSING, "device", "switch-01"),
    )
    compliance = ComplianceScoreCalculator().score((80, 60, 40))

    assert risk == 90
    assert RiskCalculator().severity_for_score(risk).level == "critical"
    assert compliance == 40


def test_evaluation_rule_registry_rejects_duplicates() -> None:
    registry = EvaluationRuleRegistry()
    rule = _rule()

    registry.register(rule)

    assert registry.get("risk-rule") is rule
    with pytest.raises(RuleRegistrationError):
        registry.register(rule)
