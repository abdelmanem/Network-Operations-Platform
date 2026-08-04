"""Rule metadata models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.app.compliance.domain.enums import RuleStatus


@dataclass(frozen=True, slots=True)
class RuleMetadata:
    """Descriptive metadata for a compliance rule."""

    version: str
    status: RuleStatus = RuleStatus.ACTIVE
    owner: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    references: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
