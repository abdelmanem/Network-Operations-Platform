"""Lifecycle definitions for policies."""

from __future__ import annotations

from enum import StrEnum


class PolicyLifecycle(StrEnum):
    """Immutable lifecycle states for a Policy."""

    DRAFT = "Draft"
    REVIEW = "Review"
    APPROVED = "Approved"
    PUBLISHED = "Published"
    DEPRECATED = "Deprecated"
    ARCHIVED = "Archived"
