"""Normalization rule registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.normalization.rules import NormalizationRule
from backend.app.parsers.result import ParserResult


@dataclass(slots=True)
class RuleRegistry:
    """Register normalization rules."""

    _rules: dict[str, NormalizationRule] = field(default_factory=dict)

    def register(self, rule: NormalizationRule) -> None:
        """Register a normalization rule."""

        self._rules[rule.name] = rule

    def names(self) -> tuple[str, ...]:
        """Return rule names."""

        return tuple(self._rules)

    def apply_all(self, result: ParserResult) -> tuple[str, ...]:
        """Apply all registered rules to a parser result."""

        applied: list[str] = []
        for rule in self._rules.values():
            rule.apply(result)
            applied.append(rule.name)
        return tuple(applied)
