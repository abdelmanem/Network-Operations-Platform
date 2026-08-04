"""Normalization rule definitions."""

from __future__ import annotations

from typing import Protocol

from backend.app.parsers.result import ParserResult


class NormalizationRule(Protocol):
    """Protocol for normalization rules."""

    name: str

    def apply(self, result: ParserResult) -> None:
        """Apply a normalization rule."""
