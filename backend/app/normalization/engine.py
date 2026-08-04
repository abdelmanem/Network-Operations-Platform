"""Normalization engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.app.normalization.mapper import NormalizationMapper
from backend.app.normalization.registry import RuleRegistry
from backend.app.normalization.validator import NormalizationValidator
from backend.app.parsers.result import ParserResult
from backend.app.snapshot.entities import InventorySnapshot


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Normalized inventory output."""

    snapshot: InventorySnapshot
    applied_rules: tuple[str, ...]
    normalized_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class NormalizationEngine:
    """Coordinate normalization of parser output."""

    mapper: NormalizationMapper = field(default_factory=NormalizationMapper)
    validator: NormalizationValidator = field(default_factory=NormalizationValidator)
    rule_registry: RuleRegistry = field(default_factory=RuleRegistry)

    def normalize(self, result: ParserResult) -> NormalizationResult:
        """Normalize parser output into canonical snapshot entities."""

        self.validator.validate_parsed_result(result)
        applied_rules = self.rule_registry.apply_all(result)
        snapshot = self.mapper.to_snapshot(result)
        self.validator.validate_snapshot(snapshot)
        return NormalizationResult(snapshot=snapshot, applied_rules=applied_rules)
