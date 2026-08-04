"""Application metadata primitives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplicationMetadata:
    """Immutable application metadata."""

    name: str
    version: str
    package: str
    description: str
