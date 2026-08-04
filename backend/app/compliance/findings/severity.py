"""Finding severity models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.app.compliance.domain.value_objects import ComplianceValueObject


class SeverityLevel(StrEnum):
    """Compliance severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Severity(ComplianceValueObject):
    """Immutable severity value object."""

    level: SeverityLevel
    score: int = 0
    label: str | None = None

    @property
    def components(self) -> tuple[object, ...]:
        """Return the ordered components that define equality."""

        return (self.level, self.score, self.label)
