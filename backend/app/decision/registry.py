"""Registry for decision rule definitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.decision.models import DecisionRuleDefinition


@dataclass(slots=True)
class DecisionRegistry:
    """Register and retrieve decision rule definitions."""

    _rules: dict[str, DecisionRuleDefinition] = field(default_factory=dict)

    def register(self, rule: DecisionRuleDefinition) -> DecisionRuleDefinition:
        if rule.code in self._rules:
            raise ValueError(f"Decision rule {rule.code!r} is already registered.")
        self._rules[rule.code] = rule
        return rule

    def get(self, code: str) -> DecisionRuleDefinition:
        try:
            return self._rules[code]
        except KeyError as exc:
            raise KeyError(f"Unknown decision rule: {code!r}") from exc

    def values(self) -> tuple[DecisionRuleDefinition, ...]:
        return tuple(self._rules.values())
