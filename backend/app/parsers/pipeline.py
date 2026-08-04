"""Parser pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.parsers.base import BaseParser
from backend.app.parsers.context import ParserContext
from backend.app.parsers.exceptions import (
    ParserConfigurationError,
    ParserExecutionError,
)
from backend.app.parsers.registry import ParserRegistry
from backend.app.parsers.result import ParserResult


@dataclass(slots=True)
class ParserPipeline:
    """Resolve and execute parsers."""

    registry: ParserRegistry

    def parse(self, context: ParserContext, raw_output: object) -> ParserResult:
        """Parse a raw payload using the configured registry."""

        parser = self._resolve_parser(context)
        try:
            return parser.parse(context, raw_output)
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ParserExecutionError(f"Parser '{parser.name}' failed.") from exc

    def _resolve_parser(self, context: ParserContext) -> BaseParser:
        if context.parser_name is not None:
            return self.registry.get(context.parser_name)

        parsers = self.registry.select(context.input_format)
        if not parsers:
            raise ParserConfigurationError(
                f"No parser registered for format '{context.input_format}'."
            )
        return parsers[0]
