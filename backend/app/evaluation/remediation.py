"""Remediation recommendation generation."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.comparison.diff import Difference
from backend.app.compliance.findings.models import Recommendation
from backend.app.compliance.findings.severity import Severity
from backend.app.compliance.rules.base import Rule


@dataclass(slots=True)
class RecommendationBuilder:
    """Build remediation guidance for failed evaluations."""

    def build(
        self,
        rule: Rule,
        difference: Difference,
        severity: Severity,
    ) -> Recommendation:
        """Create a remediation recommendation."""

        return Recommendation(
            summary=(
                f"Remediate {difference.subject_type} drift "
                f"for {difference.subject_id}."
            ),
            rationale=(
                f"Rule {rule.key} failed with severity "
                f"{severity.label or severity.level.value}."
            ),
            steps=(
                "Validate NetBox source-of-truth data.",
                "Validate live observed device state.",
                "Apply an approved operational change outside this platform.",
                "Run discovery and comparison again.",
            ),
        )
