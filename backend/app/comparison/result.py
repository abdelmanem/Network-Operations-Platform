"""Comparison result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.compliance.findings.models import Finding


@dataclass(frozen=True, slots=True)
class ComparisonMetrics:
    """Inventory comparison metrics."""

    total_differences: int
    total_findings: int
    missing: int = 0
    unexpected: int = 0
    modified: int = 0
    conflict: int = 0
    duplicate: int = 0
    unsupported: int = 0
    unknown: int = 0

    @classmethod
    def from_differences(
        cls,
        differences: tuple[Difference, ...],
        findings: tuple[Finding, ...],
    ) -> ComparisonMetrics:
        """Create metrics from differences and findings."""

        counts = {difference_type: 0 for difference_type in DifferenceType}
        for difference in differences:
            counts[difference.difference_type] += 1
        return cls(
            total_differences=len(differences),
            total_findings=len(findings),
            missing=counts[DifferenceType.MISSING],
            unexpected=counts[DifferenceType.UNEXPECTED],
            modified=counts[DifferenceType.MODIFIED],
            conflict=counts[DifferenceType.CONFLICT],
            duplicate=counts[DifferenceType.DUPLICATE],
            unsupported=counts[DifferenceType.UNSUPPORTED],
            unknown=counts[DifferenceType.UNKNOWN],
        )


@dataclass(frozen=True, slots=True)
class InventoryComparisonResult:
    """Output of NetBox-to-live inventory comparison."""

    differences: tuple[Difference, ...] = field(default_factory=tuple)
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    metrics: ComparisonMetrics | None = None
    compared_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_compliant(self) -> bool:
        """Return whether no inventory drift was detected."""

        return not self.differences
