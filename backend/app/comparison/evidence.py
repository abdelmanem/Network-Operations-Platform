"""Evidence generation for inventory differences."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.comparison.diff import Difference
from backend.app.compliance.findings.evidence import Evidence


@dataclass(slots=True)
class EvidenceGenerator:
    """Create compliance evidence from inventory differences."""

    source: str = "comparison-engine"

    def from_difference(self, difference: Difference) -> Evidence:
        """Build one evidence record for a difference."""

        return Evidence.create(
            self.source,
            difference.description or "Inventory difference detected.",
            reference=difference.key,
            details={
                "difference_type": difference.difference_type.value,
                "subject_type": difference.subject_type,
                "subject_id": difference.subject_id,
                "field_name": difference.field_name,
                "expected": difference.expected,
                "observed": difference.observed,
                "metadata": dict(difference.metadata),
            },
            captured_at=difference.detected_at,
        )
