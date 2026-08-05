"""Evaluation rule registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.compliance.rules.base import Rule
from backend.app.evaluation.exceptions import RuleRegistrationError


@dataclass(slots=True)
class EvaluationRuleRegistry:
    """Register executable evaluation rules."""

    _rules: dict[str, Rule] = field(default_factory=dict)

    def register(self, rule: Rule) -> None:
        """Register one evaluation rule."""

        if rule.key in self._rules:
            raise RuleRegistrationError(f"Rule {rule.key!r} is already registered.")
        self._rules[rule.key] = rule

    def get(self, key: str) -> Rule:
        """Return one rule by key."""

        try:
            return self._rules[key]
        except KeyError as exc:
            raise RuleRegistrationError(f"Unknown evaluation rule: {key!r}") from exc

    def values(self) -> tuple[Rule, ...]:
        """Return all registered rules."""

        return tuple(self._rules.values())
