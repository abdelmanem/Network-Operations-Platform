"""Parser execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class ParserInputFormat(StrEnum):
    """Supported raw input formats."""

    TEXT = "text"
    JSON = "json"
    XML = "xml"
    KEY_VALUE = "key_value"


@dataclass(frozen=True, slots=True)
class ParserContext:
    """Context shared across parser execution."""

    source: str
    input_format: ParserInputFormat
    parser_name: str | None = None
    run_id: UUID = field(default_factory=uuid4)
    metadata: dict[str, object] = field(default_factory=dict)
