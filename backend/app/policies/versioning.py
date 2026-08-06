"""Versioning helpers for policy definitions."""

from __future__ import annotations

from enum import StrEnum


class VersionChange(StrEnum):
    """Supported policy version increments."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
