from __future__ import annotations

from backend.app.compliance.comparison.models import ComparisonMetrics, ComparisonTarget
from backend.app.compliance.domain.enums import ComparisonStatus, RuleStatus
from backend.app.compliance.findings.severity import Severity, SeverityLevel
from backend.app.compliance.policies.models import Baseline, Policy
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata


def test_comparison_result_creation_uses_model_contract() -> None:
    baseline = Baseline.create("baseline")
    rule = Rule.create(
        "rule-1",
        "Rule 1",
        RuleMetadata(version="1.0", status=RuleStatus.ACTIVE),
        baseline=baseline,
    )
    policy = Policy.create("policy-1", rules=(rule,), baselines=(baseline,))
    target = ComparisonTarget(
        policy=policy,
        baseline=baseline,
        subject_type="device",
        subject_id="device-1",
    )

    severity = Severity(level=SeverityLevel.MEDIUM, score=50)
    metrics = ComparisonMetrics(
        total_findings=1,
        compliant_checks=0,
        failed_checks=1,
        warning_checks=0,
    )

    assert target.policy_id == policy.id
    assert target.baseline_id == baseline.id
    assert severity.level == SeverityLevel.MEDIUM
    assert metrics.total_findings == 1
    assert ComparisonStatus.NON_COMPLIANT.value == "non_compliant"
