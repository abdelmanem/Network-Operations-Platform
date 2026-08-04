"""Parser framework."""

from backend.app.parsers.base import BaseParser
from backend.app.parsers.context import ParserContext, ParserInputFormat
from backend.app.parsers.exceptions import (
    ParserConfigurationError,
    ParserError,
    ParserExecutionError,
    ParserRegistrationError,
    ParserValidationError,
)
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.registry import ParserRegistry
from backend.app.parsers.result import ParsedRecord, ParserResult

__all__ = [
    "BaseParser",
    "ParsedRecord",
    "ParserConfigurationError",
    "ParserContext",
    "ParserError",
    "ParserExecutionError",
    "ParserInputFormat",
    "ParserPipeline",
    "ParserRegistry",
    "ParserRegistrationError",
    "ParserResult",
    "ParserValidationError",
]
