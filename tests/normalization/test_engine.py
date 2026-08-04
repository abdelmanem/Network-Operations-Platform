from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from backend.app.normalization.engine import NormalizationEngine
from backend.app.normalization.registry import RuleRegistry
from backend.app.parsers.context import ParserInputFormat
from backend.app.parsers.result import ParsedRecord, ParserResult


@dataclass(slots=True)
class DummyRule:
    name: str
    calls: list[str]

    def apply(self, result: ParserResult) -> None:
        self.calls.append(result.source)


def test_normalization_engine_applies_rules_and_maps_snapshot() -> None:
    registry = RuleRegistry()
    calls: list[str] = []
    registry.register(DummyRule(name="rule-1", calls=calls))
    engine = NormalizationEngine(rule_registry=registry)
    result = ParserResult(
        parser_name="device-parser",
        source="console",
        input_format=ParserInputFormat.TEXT,
        records=(
            ParsedRecord(
                kind="device",
                payload={"device_id": "device-1", "name": "Switch 1"},
            ),
        ),
        captured_at=datetime.now(UTC),
    )

    normalized = engine.normalize(result)

    assert normalized.applied_rules == ("rule-1",)
    assert calls == ["console"]
    assert normalized.snapshot.devices[0].device_id == "device-1"
