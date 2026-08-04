"""Parser registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.parsers.base import BaseParser
from backend.app.parsers.context import ParserInputFormat
from backend.app.parsers.exceptions import ParserRegistrationError


@dataclass(slots=True)
class ParserRegistry:
    """Register and resolve parser implementations."""

    _parsers: dict[str, BaseParser] = field(default_factory=dict)

    def register(self, parser: BaseParser) -> None:
        """Register a parser instance."""

        if parser.name in self._parsers:
            raise ParserRegistrationError(
                f"Parser '{parser.name}' is already registered."
            )

        self._parsers[parser.name] = parser

    def get(self, name: str) -> BaseParser:
        """Return a parser by name."""

        try:
            return self._parsers[name]
        except KeyError as exc:
            raise ParserRegistrationError(f"Unknown parser: {name}") from exc

    def select(self, input_format: ParserInputFormat) -> tuple[BaseParser, ...]:
        """Return parsers that support a format."""

        return tuple(
            parser for parser in self._parsers.values() if parser.supports(input_format)
        )

    def names(self) -> tuple[str, ...]:
        """Return registered parser names."""

        return tuple(self._parsers)
