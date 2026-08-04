"""Rule registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from backend.app.compliance.rules.base import Rule


@dataclass(slots=True)
class RuleRegistry:
    """Register and resolve compliance rules."""

    _rules_by_id: dict[UUID, Rule] = field(default_factory=dict)
    _rules_by_key: dict[str, Rule] = field(default_factory=dict)

    def register(self, rule: Rule) -> None:
        """Register a rule."""

        if rule.id in self._rules_by_id:
            raise ValueError(f"Rule id {rule.id!r} is already registered.")
        if rule.key in self._rules_by_key:
            raise ValueError(f"Rule key '{rule.key}' is already registered.")

        self._rules_by_id[rule.id] = rule
        self._rules_by_key[rule.key] = rule

    def get(self, rule_id: UUID) -> Rule:
        """Return a rule by identity."""

        try:
            return self._rules_by_id[rule_id]
        except KeyError as exc:
            raise KeyError(f"Unknown rule id: {rule_id!r}") from exc

    def get_by_key(self, key: str) -> Rule:
        """Return a rule by key."""

        try:
            return self._rules_by_key[key]
        except KeyError as exc:
            raise KeyError(f"Unknown rule key: {key!r}") from exc

    def values(self) -> tuple[Rule, ...]:
        """Return registered rules."""

        return tuple(self._rules_by_id.values())
