"""Policy framework exceptions."""

from __future__ import annotations


class PolicyValidationError(ValueError):
    """Raised when a policy definition fails validation."""


class InvalidVersionError(PolicyValidationError):
    """Raised when a policy version is malformed."""


class CircularInheritanceError(PolicyValidationError):
    """Raised when policy inheritance contains a cycle."""


class MissingBaselineError(PolicyValidationError):
    """Raised when a policy references a missing baseline."""


class InvalidAssignmentError(PolicyValidationError):
    """Raised when an assignment definition is invalid."""
