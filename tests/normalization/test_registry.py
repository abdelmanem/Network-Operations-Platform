from __future__ import annotations

from dataclasses import dataclass

from backend.app.normalization.registry import RuleRegistry
from backend.app.parsers.context import ParserInputFormat
from backend.app.parsers.result import ParsedRecord, ParserResult


@dataclass(slots=True)
class DummyRule:
    name: str
    calls: list[str]

    def apply(self, result: ParserResult) -> None:
        self.calls.append(result.parser_name)


def test_rule_registry_registers_and_applies_rules() -> None:
    registry = RuleRegistry()
    calls: list[str] = []
    rule = DummyRule(name="rule-1", calls=calls)
    result = ParserResult(
        parser_name="parser-1",
        source="console",
        input_format=ParserInputFormat.TEXT,
        records=(ParsedRecord(kind="device", payload={"device_id": "device-1"}),),
    )

    registry.register(rule)
    applied = registry.apply_all(result)

    assert applied == ("rule-1",)
    assert calls == ["parser-1"]
    assert registry.names() == ("rule-1",)
