"""Parser result models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.app.parsers.context import ParserInputFormat


@dataclass(frozen=True, slots=True)
class ParsedRecord:
    """A single structured parser record."""

    kind: str
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ParserResult:
    """Structured output emitted by a parser."""

    parser_name: str
    source: str
    input_format: ParserInputFormat
    records: tuple[ParsedRecord, ...]
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = field(default_factory=dict)
