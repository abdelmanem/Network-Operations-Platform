"""Normalization framework."""

from backend.app.normalization.engine import NormalizationEngine, NormalizationResult
from backend.app.normalization.mapper import NormalizationMapper
from backend.app.normalization.registry import RuleRegistry
from backend.app.normalization.rules import NormalizationRule
from backend.app.normalization.validator import NormalizationValidator

__all__ = [
    "NormalizationEngine",
    "NormalizationMapper",
    "NormalizationResult",
    "NormalizationRule",
    "NormalizationValidator",
    "RuleRegistry",
]
