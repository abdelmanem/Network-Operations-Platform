from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.decision import (
    DecisionContext,
    DecisionEngine,
    DecisionRegistry,
    DecisionResult,
    DecisionStatus,
)
from backend.app.evaluation.context import (
    EvaluationStatus,
    PolicyEvaluationResult,
    RuleEvaluationResult,
)


def _policy_evaluation_result(
    status: EvaluationStatus,
    rule_statuses: tuple[EvaluationStatus, ...],
) -> PolicyEvaluationResult:
    return PolicyEvaluationResult(
        policy_id=uuid4(),
        policy_key="policy-1",
        version="1.0.0",
        status=status,
        risk_score=0,
        compliance_score=100,
        rule_results=tuple(
            RuleEvaluationResult(
                rule_id=uuid4(),
                rule_key=f"rule-{index + 1}",
                difference=None,  # type: ignore[arg-type]
                status=rule_status,
                passed=rule_status == EvaluationStatus.COMPLIANT,
                risk_score=10,
                severity=0,  # type: ignore[assignment]
                evidence=(),
            )
            for index, rule_status in enumerate(rule_statuses)
        ),
    )


def test_decision_engine_decides_pass_for_compliant_policy() -> None:
    policy_result = _policy_evaluation_result(
        EvaluationStatus.COMPLIANT,
        (EvaluationStatus.COMPLIANT,),
    )
    context = DecisionContext(
        evaluation_id=uuid4(),
        evaluation_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        decision_timestamp=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        policy_results=(policy_result,),
        evaluator_version="1.0.0",
    )

    decision = DecisionEngine().decide(context)

    assert len(decision) == 1
    assert decision[0].decision_status is DecisionStatus.PASS
    assert decision[0].confidence == 100
    assert decision[0].policy_version == "1.0.0"
    assert decision[0].triggered_rules == ("rule-1",)
    assert "compliant" in decision[0].reasoning


def test_decision_engine_decides_fail_for_non_compliant_policy() -> None:
    policy_result = _policy_evaluation_result(
        EvaluationStatus.NON_COMPLIANT,
        (EvaluationStatus.NON_COMPLIANT,),
    )
    context = DecisionContext(policy_results=(policy_result,))

    decision = DecisionEngine().decide(context)

    assert decision[0].decision_status is DecisionStatus.FAIL
    assert decision[0].confidence == 100
    assert decision[0].triggered_rules == ("rule-1",)
    assert decision[0].reasoning.startswith("One or more")


def test_decision_engine_returns_not_applicable_when_no_rules() -> None:
    policy_result = PolicyEvaluationResult(
        policy_id=uuid4(),
        policy_key="policy-2",
        version="2.0.0",
        status=EvaluationStatus.NOT_APPLICABLE,
        risk_score=0,
        compliance_score=100,
        rule_results=(),
    )
    context = DecisionContext(policy_results=(policy_result,))

    decision = DecisionEngine().decide(context)

    assert decision[0].decision_status is DecisionStatus.NOT_APPLICABLE
    assert decision[0].confidence == 0
    assert decision[0].triggered_rules == ()
    assert decision[0].reasoning.startswith("No policy rules")


def test_decision_engine_is_idempotent_with_fixed_context() -> None:
    policy_result = _policy_evaluation_result(
        EvaluationStatus.COMPLIANT,
        (EvaluationStatus.COMPLIANT, EvaluationStatus.WAIVED),
    )
    timestamp = datetime(2026, 1, 2, tzinfo=UTC)
    context = DecisionContext(
        evaluation_id=uuid4(),
        evaluation_timestamp=timestamp,
        decision_timestamp=timestamp,
        policy_results=(policy_result,),
        evaluator_version="1.0.0",
    )

    engine = DecisionEngine()
    first = engine.decide(context)
    second = engine.decide(context)

    assert first == second
    assert isinstance(first[0], DecisionResult)


def test_decision_registry_can_register_rules() -> None:
    registry = DecisionRegistry()
    engine = DecisionEngine(registry=registry)

    assert registry.values()
    assert engine.registry is registry
