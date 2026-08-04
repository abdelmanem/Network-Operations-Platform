from __future__ import annotations

from uuid import uuid4

import pytest
from backend.app.compliance.domain.enums import RuleStatus
from backend.app.compliance.rules.base import Rule
from backend.app.compliance.rules.metadata import RuleMetadata
from backend.app.compliance.rules.registry import RuleRegistry


def test_rule_registry_registers_and_resolves_rules() -> None:
    registry = RuleRegistry()
    rule = Rule.create(
        "rule-1",
        "Rule 1",
        RuleMetadata(version="1.0", status=RuleStatus.ACTIVE),
    )

    registry.register(rule)

    assert registry.get(rule.id) is rule
    assert registry.get_by_key("rule-1") is rule
    assert registry.values() == (rule,)


def test_rule_registry_rejects_duplicates() -> None:
    registry = RuleRegistry()
    rule = Rule.create(
        "rule-1",
        "Rule 1",
        RuleMetadata(version="1.0", status=RuleStatus.ACTIVE),
    )
    registry.register(rule)

    with pytest.raises(ValueError):
        registry.register(rule)

    duplicate_key = Rule(
        id=uuid4(),
        key="rule-1",
        name="Rule 2",
        metadata=RuleMetadata(version="1.0", status=RuleStatus.ACTIVE),
    )

    with pytest.raises(ValueError):
        registry.register(duplicate_key)
