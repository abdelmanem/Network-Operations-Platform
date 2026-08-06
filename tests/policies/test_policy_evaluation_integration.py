from __future__ import annotations

from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.comparison.result import InventoryComparisonResult
from backend.app.compliance.domain.enums import RuleStatus
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.evaluation import (
    EvaluationContext,
    EvaluationEngine,
    EvaluationStatus,
)
from backend.app.policies.compiler import PolicyCompiler
from backend.app.policies.models import (
    BaselineReference,
    Policy,
    PolicyAssignment,
    PolicyPackage,
    PolicyScope,
    PolicyVersion,
    RuleReference,
)
from backend.app.policies.versioning import VersionChange


def _policy_fixture() -> Policy:
    return Policy.create(
        key="policy-1",
        name="Vendor policy",
        version=PolicyVersion.create("1.0.0"),
        rules=(RuleReference(key="rule-1", name="Rule One"),),
        baselines=(BaselineReference(key="baseline-1", name="Baseline One"),),
        assignments=(PolicyAssignment(scope=PolicyScope.VENDOR, value="Cisco"),),
    )


def _rule() -> Rule:
    return Rule.create(
        "rule-1",
        "Rule One",
        RuleMetadata(version="1.0", status=RuleStatus.ACTIVE),
        expected_state={
            "rule_type": "equals",
            "subject_type": "device",
            "field_name": "serial",
            "difference_type": DifferenceType.MODIFIED,
            "risk_score": 90,
        },
    )


def _comparison_result() -> InventoryComparisonResult:
    return InventoryComparisonResult(
        differences=(
            Difference.create(
                DifferenceType.MODIFIED,
                "device",
                "switch-01",
                field_name="serial",
                expected="ABC",
                observed="XYZ",
            ),
        )
    )


def test_policy_compiler_produces_immutable_package() -> None:
    policy = _policy_fixture()
    package = PolicyCompiler().compile(policy)

    assert isinstance(package, PolicyPackage)
    assert package.policy_key == "policy-1"
    assert package.version.as_string() == "1.0.0"
    assert package.compiled_at is not None


def test_policy_package_resolves_to_executable_policy(monkeypatch) -> None:
    package = PolicyCompiler().compile(_policy_fixture())
    rule = _rule()

    from backend.app.evaluation.registry import EvaluationRuleRegistry
    from backend.app.policies.evaluation import PolicyPackageResolver

    registry = EvaluationRuleRegistry()
    registry.register(rule)

    resolver = PolicyPackageResolver(rule_registry=registry)
    policy = resolver.resolve((package,))[0]

    assert policy.id == package.policy_id
    assert policy.name == package.policy_key
    assert policy.rules[0].key == "rule-1"
    assert policy.tags == ("vendor:Cisco",)


def test_policy_evaluation_engine_with_compiled_package() -> None:
    policy = _policy_fixture()
    package = PolicyCompiler().compile(policy)
    rule = _rule()

    from backend.app.evaluation.registry import EvaluationRuleRegistry

    registry = EvaluationRuleRegistry()
    registry.register(rule)

    engine = EvaluationEngine()
    engine.policy_evaluator = engine.policy_evaluator
    engine.package_resolver.rule_registry = registry

    context = EvaluationContext(
        comparison_result=_comparison_result(),
        metadata={"vendor": "Cisco"},
    )

    decision = engine.evaluate(context, (package,))

    assert decision.status == EvaluationStatus.NON_COMPLIANT
    assert decision.metrics is not None
    assert decision.metrics.total_rules == 1
    assert decision.risk_score == 90
    assert decision.compliance_score == 10
    assert decision.policy_results[0].policy_key == "policy-1"
    assert decision.policy_results[0].version == "1.0.0"


def test_policy_version_resolution_uses_latest_package() -> None:
    policy = _policy_fixture()
    package_v1 = PolicyCompiler().compile(policy)
    package_v2 = PolicyCompiler().compile(policy.bump_version(VersionChange.MINOR))
    rule = _rule()

    from backend.app.evaluation.registry import EvaluationRuleRegistry

    registry = EvaluationRuleRegistry()
    registry.register(rule)

    engine = EvaluationEngine()
    engine.package_resolver.rule_registry = registry

    context = EvaluationContext(
        comparison_result=_comparison_result(),
        metadata={"vendor": "Cisco"},
    )

    decision = engine.evaluate(context, (package_v1, package_v2))
    assert decision.policy_results[0].version == "1.1.0"


def test_policy_scope_prevents_non_matching_vendor() -> None:
    policy = _policy_fixture()
    package = PolicyCompiler().compile(policy)
    rule = _rule()

    from backend.app.evaluation.registry import EvaluationRuleRegistry

    registry = EvaluationRuleRegistry()
    registry.register(rule)

    engine = EvaluationEngine()
    engine.package_resolver.rule_registry = registry

    context = EvaluationContext(
        comparison_result=_comparison_result(),
        metadata={"vendor": "Juniper"},
    )

    decision = engine.evaluate(context, (package,))
    assert decision.status == EvaluationStatus.NOT_APPLICABLE
    assert decision.metrics is not None
    assert decision.metrics.total_rules == 0


def test_policy_inheritance_is_applied_in_package_resolution() -> None:
    base = _policy_fixture()
    child = _policy_fixture().with_inheritance((base.id,))
    package_base = PolicyCompiler().compile(base)
    package_child = PolicyCompiler().compile(child)
    rule = _rule()

    from backend.app.evaluation.registry import EvaluationRuleRegistry

    registry = EvaluationRuleRegistry()
    registry.register(rule)

    engine = EvaluationEngine()
    engine.package_resolver.rule_registry = registry

    context = EvaluationContext(
        comparison_result=_comparison_result(),
        metadata={"vendor": "Cisco"},
    )

    decision = engine.evaluate(context, (package_child, package_base))
    assert decision.metrics is not None
    assert decision.metrics.total_rules == 1
    assert decision.risk_score == 90
