from __future__ import annotations

from dataclasses import dataclass

import pytest
from backend.app.parsers.base import BaseParser
from backend.app.parsers.context import ParserContext, ParserInputFormat
from backend.app.parsers.exceptions import (
    ParserConfigurationError,
    ParserExecutionError,
)
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.registry import ParserRegistry
from backend.app.parsers.result import ParsedRecord, ParserResult


@dataclass(slots=True)
class DummyParser(BaseParser):
    records: tuple[ParsedRecord, ...] = ()
    fail_with: Exception | None = None

    def parse(self, context: ParserContext, raw_output: object) -> ParserResult:
        if self.fail_with is not None:
            raise self.fail_with
        return ParserResult(
            parser_name=self.name,
            source=context.source,
            input_format=context.input_format,
            records=self.records,
        )


def test_parser_pipeline_selects_parser_by_format() -> None:
    registry = ParserRegistry()
    parser = DummyParser(
        name="text-parser",
        supported_formats=frozenset({ParserInputFormat.TEXT}),
        records=(ParsedRecord(kind="device", payload={"device_id": "device-1"}),),
    )
    registry.register(parser)
    pipeline = ParserPipeline(registry=registry)
    context = ParserContext(source="console", input_format=ParserInputFormat.TEXT)

    result = pipeline.parse(context, raw_output="raw text")

    assert result.parser_name == "text-parser"
    assert result.records[0].payload["device_id"] == "device-1"


def test_parser_pipeline_respects_explicit_parser_name() -> None:
    registry = ParserRegistry()
    parser = DummyParser(
        name="json-parser",
        supported_formats=frozenset({ParserInputFormat.JSON}),
    )
    registry.register(parser)
    pipeline = ParserPipeline(registry=registry)
    context = ParserContext(
        source="api",
        input_format=ParserInputFormat.TEXT,
        parser_name="json-parser",
    )

    result = pipeline.parse(context, raw_output={})

    assert result.parser_name == "json-parser"


def test_parser_pipeline_raises_for_missing_parser() -> None:
    pipeline = ParserPipeline(registry=ParserRegistry())
    context = ParserContext(source="console", input_format=ParserInputFormat.TEXT)

    with pytest.raises(ParserConfigurationError):
        pipeline.parse(context, raw_output="raw text")


def test_parser_pipeline_wraps_parser_failures() -> None:
    registry = ParserRegistry()
    registry.register(
        DummyParser(
            name="text-parser",
            supported_formats=frozenset({ParserInputFormat.TEXT}),
            fail_with=ValueError("boom"),
        )
    )
    pipeline = ParserPipeline(registry=registry)
    context = ParserContext(source="console", input_format=ParserInputFormat.TEXT)

    with pytest.raises(ParserExecutionError):
        pipeline.parse(context, raw_output="raw text")
