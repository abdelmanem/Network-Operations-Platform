"""Policy compilation and evaluation engine."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.policies.models import Policy, PolicyPackage
from backend.app.policies.validation import PolicyValidator


class PolicyEngine:
    """Compile policies into immutable evaluation packages."""

    def __init__(self, validator: PolicyValidator | None = None) -> None:
        self.validator = validator or PolicyValidator()

    def validate(self, policy: Policy) -> Policy:
        self.validator.validate(policy)
        return policy

    def compile(self, policy: Policy) -> PolicyPackage:
        self.validate(policy)
        return PolicyPackage(
            policy_id=policy.id,
            policy_key=policy.key,
            version=policy.version,
            rules=policy.rules,
            baselines=policy.baselines,
            assignments=policy.assignments,
            inherited_ids=policy.inheritance,
            compiled_at=datetime.now(UTC),
        )

    def evaluate(self, policy: Policy) -> PolicyPackage:
        return self.compile(policy)
