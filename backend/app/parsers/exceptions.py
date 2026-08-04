"""Parser exception hierarchy."""

from __future__ import annotations

from backend.app.core.exceptions import ApplicationError


class ParserError(ApplicationError):
    """Base class for parser failures."""


class ParserConfigurationError(ParserError):
    """Raised when parser configuration is invalid."""


class ParserRegistrationError(ParserError):
    """Raised when parser registration fails."""


class ParserExecutionError(ParserError):
    """Raised when parser execution fails."""


class ParserValidationError(ParserError):
    """Raised when parser output is invalid."""
