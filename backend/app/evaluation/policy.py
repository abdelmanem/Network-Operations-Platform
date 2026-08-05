"""Policy selection and evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.compliance.policies.models import Policy
from backend.app.compliance.rules.base import Rule
from backend.app.evaluation.context import EvaluationContext


@dataclass(slots=True)
class PolicyEvaluator:
    """Select policy rules applicable to an evaluation context."""

    def applicable_rules(
        self,
        policies: tuple[Policy, ...],
        context: EvaluationContext,
    ) -> tuple[Rule, ...]:
        """Return rules from enabled policies matching scope metadata."""

        rules: list[Rule] = []
        seen: set[str] = set()
        for policy in policies:
            if not policy.enabled or not self._policy_applies(policy, context):
                continue
            for rule in policy.rules:
                if self._rule_applies(rule, context) and rule.key not in seen:
                    rules.append(rule)
                    seen.add(rule.key)
        return tuple(rules)

    def _policy_applies(self, policy: Policy, context: EvaluationContext) -> bool:
        if not policy.tags:
            return True
        return self._tags_apply(policy.tags, context)

    def _rule_applies(self, rule: Rule, context: EvaluationContext) -> bool:
        return self._tags_apply(rule.metadata.tags, context)

    @staticmethod
    def _tags_apply(tags: tuple[str, ...], context: EvaluationContext) -> bool:
        if not tags:
            return True
        required = {
            tag.split(":", 1)[0]: tag.split(":", 1)[1] for tag in tags if ":" in tag
        }
        if "site" in required and required["site"] != context.site:
            return False
        if "role" in required and required["role"] != context.device_role:
            return False
        if "platform" in required and required["platform"] != context.platform:
            return False
        return True
