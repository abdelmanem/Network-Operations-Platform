from __future__ import annotations

from dataclasses import dataclass

import pytest
from backend.app.parsers.base import BaseParser
from backend.app.parsers.context import ParserContext, ParserInputFormat
from backend.app.parsers.exceptions import ParserRegistrationError
from backend.app.parsers.registry import ParserRegistry
from backend.app.parsers.result import ParserResult


@dataclass(slots=True)
class DummyParser(BaseParser):
    def parse(self, context: ParserContext, raw_output: object) -> ParserResult:
        return ParserResult(
            parser_name=self.name,
            source=context.source,
            input_format=context.input_format,
            records=(),
        )


def test_parser_registry_registers_and_selects_parsers() -> None:
    registry = ParserRegistry()
    parser = DummyParser(
        name="dummy",
        supported_formats=frozenset({ParserInputFormat.TEXT}),
    )

    registry.register(parser)

    assert registry.get("dummy") is parser
    assert registry.select(ParserInputFormat.TEXT) == (parser,)
    assert registry.names() == ("dummy",)


def test_parser_registry_rejects_duplicate_registration() -> None:
    registry = ParserRegistry()
    parser = DummyParser(
        name="dummy",
        supported_formats=frozenset({ParserInputFormat.TEXT}),
    )

    registry.register(parser)

    with pytest.raises(ParserRegistrationError):
        registry.register(parser)


def test_parser_registry_rejects_unknown_parser() -> None:
    registry = ParserRegistry()

    with pytest.raises(ParserRegistrationError):
        registry.get("missing")
