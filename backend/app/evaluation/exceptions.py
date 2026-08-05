"""Evaluation exception hierarchy."""

from __future__ import annotations

from backend.app.core.exceptions import ApplicationError


class EvaluationError(ApplicationError):
    """Base class for evaluation failures."""


class RuleEvaluationError(EvaluationError):
    """Raised when a rule cannot be evaluated."""


class PolicyEvaluationError(EvaluationError):
    """Raised when policy evaluation cannot continue."""


class RuleRegistrationError(EvaluationError):
    """Raised when rule registration fails."""
