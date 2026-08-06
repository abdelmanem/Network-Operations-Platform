"""Compliance evaluation engine orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.comparison.diff import Difference
from backend.app.compliance.findings.evidence import Evidence
from backend.app.compliance.findings.models import Recommendation
from backend.app.compliance.policies.models import Policy
from backend.app.compliance.rules.base import Rule
from backend.app.evaluation.context import (
    EvaluationContext,
    EvaluationDecision,
    EvaluationException,
    EvaluationMetrics,
    EvaluationStatus,
    RuleEvaluationResult,
)
from backend.app.evaluation.executor import RuleExecutor
from backend.app.evaluation.policy import PolicyEvaluator
from backend.app.evaluation.remediation import RecommendationBuilder
from backend.app.evaluation.scoring import ComplianceScoreCalculator, RiskCalculator


@dataclass(slots=True)
class EvaluationEngine:
    """Evaluate comparison differences against compliance policies."""

    policy_evaluator: PolicyEvaluator = field(default_factory=PolicyEvaluator)
    risk_calculator: RiskCalculator = field(default_factory=RiskCalculator)
    score_calculator: ComplianceScoreCalculator = field(
        default_factory=ComplianceScoreCalculator
    )
    recommendation_builder: RecommendationBuilder = field(
        default_factory=RecommendationBuilder
    )

    def evaluate(
        self,
        comparison_context: EvaluationContext,
        policies: tuple[Policy, ...],
    ) -> EvaluationDecision:
        """Evaluate policies and return an immutable decision."""

        rules = self.policy_evaluator.applicable_rules(policies, comparison_context)
        executor = RuleExecutor(
            risk_calculator=self.risk_calculator,
            recommendation_builder=self.recommendation_builder,
        )
        results: list[RuleEvaluationResult] = []
        for difference in comparison_context.comparison_result.differences:
            for rule in self._rules_for_difference(rules, difference):
                exception = self._exception_for(rule, difference, comparison_context)
                results.append(executor.execute(rule, difference, exception=exception))

        rule_results = tuple(results)
        risk_scores = tuple(result.risk_score for result in rule_results)
        risk_score = max(risk_scores, default=0)
        compliance_score = self.score_calculator.score(risk_scores)
        status = self._status(rule_results)
        metrics = self._metrics(
            total_rules=len(rules),
            rule_results=rule_results,
            risk_score=risk_score,
            compliance_score=compliance_score,
        )
        return EvaluationDecision(
            status=status,
            risk_score=risk_score,
            compliance_score=compliance_score,
            severity=self.risk_calculator.severity_for_score(risk_score),
            recommendations=self._recommendations(rule_results),
            evidence=self._evidence(rule_results),
            rule_results=rule_results,
            metrics=metrics,
        )

    @staticmethod
    def _rules_for_difference(
        rules: tuple[Rule, ...],
        difference: Difference,
    ) -> tuple[Rule, ...]:
        applicable: list[Rule] = []
        for rule in rules:
            subject_type = rule.expected_state.get("subject_type")
            field_name = rule.expected_state.get("field_name")
            difference_type = rule.expected_state.get("difference_type")
            if subject_type is not None and subject_type != difference.subject_type:
                continue
            if field_name is not None and field_name != difference.field_name:
                continue
            if difference_type is not None:
                if str(difference_type) != difference.difference_type.value:
                    continue
            applicable.append(rule)
        return tuple(applicable)

    @staticmethod
    def _exception_for(
        rule: Rule,
        difference: Difference,
        context: EvaluationContext,
    ) -> EvaluationException | None:
        for exception in context.exceptions:
            if exception.applies_to(rule.key, difference):
                return exception
        return None

    @staticmethod
    def _status(rule_results: tuple[RuleEvaluationResult, ...]) -> EvaluationStatus:
        if not rule_results:
            return EvaluationStatus.NOT_APPLICABLE
        if any(
            result.status == EvaluationStatus.NON_COMPLIANT for result in rule_results
        ):
            return EvaluationStatus.NON_COMPLIANT
        if all(result.status == EvaluationStatus.WAIVED for result in rule_results):
            return EvaluationStatus.WAIVED
        return EvaluationStatus.COMPLIANT

    @staticmethod
    def _metrics(
        *,
        total_rules: int,
        rule_results: tuple[RuleEvaluationResult, ...],
        risk_score: int,
        compliance_score: int,
    ) -> EvaluationMetrics:
        return EvaluationMetrics(
            total_rules=total_rules,
            evaluated_rules=len(rule_results),
            compliant=sum(
                result.status == EvaluationStatus.COMPLIANT for result in rule_results
            ),
            non_compliant=sum(
                result.status == EvaluationStatus.NON_COMPLIANT
                for result in rule_results
            ),
            waived=sum(
                result.status == EvaluationStatus.WAIVED for result in rule_results
            ),
            not_applicable=sum(
                result.status == EvaluationStatus.NOT_APPLICABLE
                for result in rule_results
            ),
            errors=sum(
                result.status == EvaluationStatus.ERROR for result in rule_results
            ),
            risk_score=risk_score,
            compliance_score=compliance_score,
        )

    @staticmethod
    def _recommendations(
        rule_results: tuple[RuleEvaluationResult, ...],
    ) -> tuple[Recommendation, ...]:
        return tuple(
            result.recommendation
            for result in rule_results
            if result.recommendation is not None
        )

    @staticmethod
    def _evidence(
        rule_results: tuple[RuleEvaluationResult, ...],
    ) -> tuple[Evidence, ...]:
        evidence: list[Evidence] = []
        for result in rule_results:
            evidence.extend(result.evidence)
        return tuple(evidence)
