from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest
from backend.app.compliance.comparison.models import ComparisonMetrics, ComparisonTarget
from backend.app.compliance.comparison.result import ComparisonResult
from backend.app.compliance.domain.entities import ComplianceEntity
from backend.app.compliance.domain.enums import ComparisonStatus, RuleStatus
from backend.app.compliance.findings.evidence import Evidence
from backend.app.compliance.findings.models import Finding, Recommendation
from backend.app.compliance.findings.severity import Severity, SeverityLevel
from backend.app.compliance.policies.models import Baseline, Policy
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata


def test_value_models_and_entities_are_immutable() -> None:
    metadata = RuleMetadata(version="1.0", status=RuleStatus.ACTIVE, tags=("core",))
    baseline = Baseline.create("baseline")
    rule = Rule.create("rule-1", "Rule 1", metadata, baseline=baseline)
    policy = Policy.create("policy-1", rules=(rule,), baselines=(baseline,))
    severity = Severity(level=SeverityLevel.HIGH, score=80, label="High")
    evidence = Evidence.create("device", "Observed mismatch")
    recommendation = Recommendation(
        summary="Align configuration",
        rationale="Observed state diverges from baseline",
        steps=("Review device state", "Apply approved change"),
    )
    finding = Finding.create(
        uuid4(),
        "Interface mismatch",
        severity,
        evidence=(evidence,),
        recommendation=recommendation,
    )
    target = ComparisonTarget(
        policy=policy,
        baseline=baseline,
        subject_type="device",
        subject_id="device-1",
    )
    result = ComparisonResult.create(
        target,
        ComparisonStatus.NON_COMPLIANT,
        findings=(finding,),
        metrics=ComparisonMetrics(
            total_findings=1,
            compliant_checks=0,
            failed_checks=1,
        ),
    )

    with pytest.raises(FrozenInstanceError):
        metadata.version = "2.0"  # type: ignore[misc]

    with pytest.raises(TypeError):
        baseline.expected_state["foo"] = "bar"  # type: ignore[index]

    with pytest.raises(TypeError):
        evidence.details["foo"] = "bar"  # type: ignore[index]

    assert isinstance(rule.id, UUID)
    assert policy.rules == (rule,)
    assert finding.evidence == (evidence,)
    assert finding.recommendation == recommendation
    assert target.policy_id == policy.id
    assert result.status == ComparisonStatus.NON_COMPLIANT
    assert result.metrics is not None
    assert result.metrics.failed_checks == 1


def test_compliance_entity_identity_comparison() -> None:
    first = ComplianceEntity(id=uuid4())
    second = ComplianceEntity(id=first.id)

    assert first.same_identity_as(second) is True
    assert first.same_identity_as(object()) is False
