from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.comparison.result import InventoryComparisonResult
from backend.app.compliance.domain.enums import RuleStatus
from backend.app.compliance.policies.models import Policy
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.evaluation import (
    EvaluationContext,
    EvaluationEngine,
    EvaluationException,
    EvaluationStatus,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "evaluation"


def _policy_from_fixture() -> Policy:
    payload = json.loads((FIXTURES / "golden_policy.json").read_text("utf-8"))
    rules = tuple(
        Rule.create(
            item["key"],
            item["name"],
            RuleMetadata(
                version="1.0",
                status=RuleStatus.ACTIVE,
                tags=tuple(item.get("tags", ())),
            ),
            expected_state={
                "rule_type": item["rule_type"],
                "subject_type": item["subject_type"],
                "field_name": item.get("field_name"),
                "difference_type": item.get("difference_type"),
                "risk_score": item["risk_score"],
            },
        )
        for item in payload["rules"]
    )
    return Policy.create(
        payload["policy"]["name"],
        rules=rules,
        tags=tuple(payload["policy"]["tags"]),
    )


def _comparison() -> InventoryComparisonResult:
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
            Difference.create(
                DifferenceType.MISSING,
                "interface",
                "switch-01:Gi1/0/2",
                expected="Gi1/0/2",
                observed=None,
            ),
        )
    )


def test_evaluation_engine_evaluates_scoped_policy_fixture() -> None:
    context = EvaluationContext(
        comparison_result=_comparison(),
        metadata={"site": "HQ", "device_role": "access", "platform": "iosxe"},
    )

    decision = EvaluationEngine().evaluate(context, (_policy_from_fixture(),))

    assert decision.status == EvaluationStatus.NON_COMPLIANT
    assert decision.risk_score == 80
    assert decision.compliance_score == 25
    assert decision.metrics is not None
    assert decision.metrics.total_rules == 2
    assert decision.metrics.non_compliant == 2
    assert len(decision.recommendations) == 2
    assert len(decision.evidence) == 2


def test_evaluation_engine_applies_temporary_waiver() -> None:
    context = EvaluationContext(
        comparison_result=_comparison(),
        metadata={"site": "HQ", "device_role": "access", "platform": "iosxe"},
        exceptions=(
            EvaluationException(
                key="waiver-1",
                reason="Approved maintenance window",
                approved_by="netops",
                rule_key="device-serial-must-match",
                subject_type="device",
                subject_id="switch-01",
                expires_at=datetime.now(UTC) + timedelta(days=1),
            ),
        ),
    )

    decision = EvaluationEngine().evaluate(context, (_policy_from_fixture(),))

    assert decision.status == EvaluationStatus.NON_COMPLIANT
    assert decision.metrics is not None
    assert decision.metrics.waived == 1
    assert decision.metrics.non_compliant == 1
    assert decision.risk_score == 70


def test_expired_exception_does_not_waive_result() -> None:
    context = EvaluationContext(
        comparison_result=_comparison(),
        metadata={"site": "HQ", "device_role": "access", "platform": "iosxe"},
        exceptions=(
            EvaluationException(
                key="expired",
                reason="Expired",
                approved_by="netops",
                rule_key="device-serial-must-match",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            ),
        ),
    )

    decision = EvaluationEngine().evaluate(context, (_policy_from_fixture(),))

    assert decision.metrics is not None
    assert decision.metrics.waived == 0
    assert decision.metrics.non_compliant == 2


def test_policy_scope_can_make_evaluation_not_applicable() -> None:
    context = EvaluationContext(
        comparison_result=_comparison(),
        metadata={"site": "Branch", "device_role": "access", "platform": "iosxe"},
    )

    decision = EvaluationEngine().evaluate(context, (_policy_from_fixture(),))

    assert decision.status == EvaluationStatus.NOT_APPLICABLE
    assert decision.metrics is not None
    assert decision.metrics.total_rules == 0
