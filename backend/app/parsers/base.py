"""Abstract parser interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.app.parsers.context import ParserContext, ParserInputFormat
from backend.app.parsers.result import ParserResult


@dataclass(slots=True)
class BaseParser(ABC):
    """Base class for all parsers."""

    name: str
    supported_formats: frozenset[ParserInputFormat]

    def supports(self, input_format: ParserInputFormat) -> bool:
        """Return whether the parser supports a raw input format."""

        return input_format in self.supported_formats

    @abstractmethod
    def parse(self, context: ParserContext, raw_output: object) -> ParserResult:
        """Parse raw transport output into structured records."""
