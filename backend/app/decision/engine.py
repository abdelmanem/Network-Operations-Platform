"""Policy decision engine that consumes evaluation results."""

from __future__ import annotations

from collections.abc import Iterable

from backend.app.decision.context import DecisionContext
from backend.app.decision.models import (
    DecisionReason,
    DecisionResult,
    DecisionRule,
    DecisionRuleDefinition,
    DecisionStatus,
    DecisionTrace,
)
from backend.app.decision.registry import DecisionRegistry
from backend.app.evaluation.context import (
    EvaluationStatus,
    PolicyEvaluationResult,
    RuleEvaluationResult,
)

DEFAULT_DECISION_RULE_DEFINITIONS: tuple[DecisionRuleDefinition, ...] = (
    DecisionRuleDefinition(
        code="policy_not_applicable",
        description="No policy rules were applicable during evaluation.",
        status=DecisionStatus.NOT_APPLICABLE,
        confidence=0,
        match_policy_statuses=(EvaluationStatus.NOT_APPLICABLE,),
        priority=100,
    ),
    DecisionRuleDefinition(
        code="policy_non_compliant",
        description="The evaluation result contains non-compliant rule outcomes.",
        status=DecisionStatus.FAIL,
        confidence=100,
        match_policy_statuses=(EvaluationStatus.NON_COMPLIANT,),
        priority=90,
    ),
    DecisionRuleDefinition(
        code="policy_error",
        description=(
            "The evaluation result contains errors and could not reach full compliance."
        ),
        status=DecisionStatus.WARNING,
        confidence=50,
        match_policy_statuses=(EvaluationStatus.ERROR,),
        priority=80,
    ),
    DecisionRuleDefinition(
        code="policy_pass",
        description=(
            "The evaluation result is compliant or waived and supports a passing "
            "decision."
        ),
        status=DecisionStatus.PASS,
        confidence=100,
        match_policy_statuses=(EvaluationStatus.COMPLIANT, EvaluationStatus.WAIVED),
        priority=70,
    ),
    DecisionRuleDefinition(
        code="policy_unknown",
        description=(
            "The evaluation result could not be mapped to a deterministic decision."
        ),
        status=DecisionStatus.UNKNOWN,
        confidence=25,
        priority=0,
    ),
)


class DecisionEngine:
    """Derive immutable decision records from policy evaluation results."""

    def __init__(self, registry: DecisionRegistry | None = None) -> None:
        self.registry = registry or DecisionRegistry()
        self._load_defaults()

    def _load_defaults(self) -> None:
        for definition in DEFAULT_DECISION_RULE_DEFINITIONS:
            if definition.code not in {rule.code for rule in self.registry.values()}:
                self.registry.register(definition)

    def decide(self, context: DecisionContext) -> tuple[DecisionResult, ...]:
        return tuple(
            self._build_decision(context, policy_result)
            for policy_result in context.policy_results
        )

    def _build_decision(
        self,
        context: DecisionContext,
        policy_result: PolicyEvaluationResult,
    ) -> DecisionResult:
        rule_results = policy_result.rule_results
        decision_status = self._determine_status(policy_result, rule_results)
        triggered_rules = tuple(self._rule_keys(rule_results))
        trace = self._build_trace(policy_result, rule_results, decision_status)
        reasoning = self._aggregate_reasoning(trace.reasons)
        return DecisionResult(
            policy_id=policy_result.policy_id,
            policy_version=policy_result.version,
            evaluation_id=context.evaluation_id,
            evaluation_timestamp=context.evaluation_timestamp,
            decision_timestamp=context.decision_timestamp,
            decision_status=decision_status,
            confidence=self._confidence(decision_status),
            reasoning=reasoning,
            triggered_rules=triggered_rules,
            evaluator_version=context.evaluator_version,
            trace=trace,
        )

    def _determine_status(
        self,
        policy_result: PolicyEvaluationResult,
        rule_results: tuple[RuleEvaluationResult, ...],
    ) -> DecisionStatus:
        if not rule_results:
            return DecisionStatus.NOT_APPLICABLE
        if any(
            result.status == EvaluationStatus.NON_COMPLIANT for result in rule_results
        ):
            return DecisionStatus.FAIL
        if any(result.status == EvaluationStatus.ERROR for result in rule_results):
            return DecisionStatus.WARNING
        if policy_result.status in (
            EvaluationStatus.COMPLIANT,
            EvaluationStatus.WAIVED,
        ):
            return DecisionStatus.PASS
        return DecisionStatus.UNKNOWN

    def _build_trace(
        self,
        policy_result: PolicyEvaluationResult,
        rule_results: tuple[RuleEvaluationResult, ...],
        decision_status: DecisionStatus,
    ) -> DecisionTrace:
        reasons = self._policy_reasons(policy_result, rule_results, decision_status)
        rules = tuple(self._summarize_rule(rule) for rule in rule_results)
        return DecisionTrace(reasons=reasons, rules=rules)

    def _policy_reasons(
        self,
        policy_result: PolicyEvaluationResult,
        rule_results: tuple[RuleEvaluationResult, ...],
        decision_status: DecisionStatus,
    ) -> tuple[DecisionReason, ...]:
        if decision_status is DecisionStatus.NOT_APPLICABLE:
            return (
                DecisionReason(
                    code="policy_not_applicable",
                    message="No policy rules were applicable during evaluation.",
                    details="The policy did not apply to the evaluated inventory.",
                ),
            )

        if decision_status is DecisionStatus.FAIL:
            non_compliant = [
                result
                for result in rule_results
                if result.status == EvaluationStatus.NON_COMPLIANT
            ]
            return (
                DecisionReason(
                    code="policy_failure",
                    message="One or more evaluated rules are non-compliant.",
                    details=f"{len(non_compliant)} rule(s) failed compliance.",
                ),
            )

        if decision_status is DecisionStatus.WARNING:
            errored = [
                result
                for result in rule_results
                if result.status == EvaluationStatus.ERROR
            ]
            return (
                DecisionReason(
                    code="policy_warning",
                    message=(
                        "The evaluation encountered errors that prevent a fully "
                        "passing decision."
                    ),
                    details=f"{len(errored)} rule(s) returned errors.",
                ),
            )

        if decision_status is DecisionStatus.PASS:
            return (
                DecisionReason(
                    code="policy_pass",
                    message="The evaluation result is compliant or waived.",
                    details="All evaluated rules support a passing decision.",
                ),
            )

        return (
            DecisionReason(
                code="policy_unknown",
                message=(
                    "The decision engine could not determine a stable decision "
                    "from evaluation results."
                ),
                details=f"Policy evaluation status: {policy_result.status.value}.",
            ),
        )

    def _summarize_rule(self, rule_result: RuleEvaluationResult) -> DecisionRule:
        return DecisionRule(
            rule_id=rule_result.rule_id,
            rule_key=rule_result.rule_key,
            status=rule_result.status,
            risk_score=rule_result.risk_score,
            confidence=self._confidence(rule_result.status),
            reason=self._rule_reason(rule_result.status),
        )

    @staticmethod
    def _rule_keys(rule_results: Iterable[RuleEvaluationResult]) -> tuple[str, ...]:
        return tuple(result.rule_key for result in rule_results)

    @staticmethod
    def _aggregate_reasoning(reasons: tuple[DecisionReason, ...]) -> str:
        return " ".join(reason.message for reason in reasons)

    @staticmethod
    def _rule_reason(status: EvaluationStatus) -> str:
        if status == EvaluationStatus.NON_COMPLIANT:
            return "Rule evaluated as non-compliant."
        if status == EvaluationStatus.ERROR:
            return "Rule evaluation produced an error."
        if status == EvaluationStatus.WAIVED:
            return "Rule evaluation was waived."
        if status == EvaluationStatus.COMPLIANT:
            return "Rule evaluated as compliant."
        if status == EvaluationStatus.NOT_APPLICABLE:
            return "Rule was not applicable."
        return "Rule evaluation status is unknown."

    @staticmethod
    def _confidence(status: DecisionStatus | EvaluationStatus) -> int:
        if (
            status == DecisionStatus.NOT_APPLICABLE
            or status == EvaluationStatus.NOT_APPLICABLE
        ):
            return 0
        if status == DecisionStatus.FAIL or status == EvaluationStatus.NON_COMPLIANT:
            return 100
        if status == DecisionStatus.WARNING or status == EvaluationStatus.ERROR:
            return 50
        if (
            status == DecisionStatus.PASS
            or status == EvaluationStatus.COMPLIANT
            or status == EvaluationStatus.WAIVED
        ):
            return 100
        return 25
