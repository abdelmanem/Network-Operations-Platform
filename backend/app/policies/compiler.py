"""Compiler for transforming policies into immutable evaluation packages."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.policies.exceptions import PolicyValidationError
from backend.app.policies.inheritance import InheritanceResolver
from backend.app.policies.models import Policy, PolicyPackage
from backend.app.policies.validation import PolicyValidator


class PolicyCompiler:
    """Compile a policy into an immutable evaluation package."""

    def __init__(
        self,
        *,
        validator: PolicyValidator | None = None,
        resolver: InheritanceResolver | None = None,
    ) -> None:
        self.validator = validator or PolicyValidator()
        self.resolver = resolver or InheritanceResolver()

    def compile(self, policy: Policy) -> PolicyPackage:
        if policy.lifecycle is not None and policy.lifecycle.name == "PUBLISHED":
            raise PolicyValidationError("Published policies cannot be recompiled")
        self.validator.validate(policy)
        return PolicyPackage(
            policy_id=policy.id,
            policy_key=policy.key,
            version=policy.version,
            rules=policy.rules,
            baselines=policy.baselines,
            assignments=policy.assignments,
            inherited_ids=self.resolver.resolve(policy),
            compiled_at=datetime.now(UTC),
        )
