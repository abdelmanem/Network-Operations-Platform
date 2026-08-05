"""NetBox comparison engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, uuid5

from backend.app.comparison.comparator import (
    DeviceComparator,
    IdentityComparator,
    InterfaceComparator,
    NeighborComparator,
    PlatformComparator,
    VLANComparator,
)
from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.comparison.evidence import EvidenceGenerator
from backend.app.comparison.filters import DifferenceFilter
from backend.app.comparison.matcher import InventoryMatcher
from backend.app.comparison.registry import DifferenceRegistry
from backend.app.comparison.result import ComparisonMetrics, InventoryComparisonResult
from backend.app.compliance.findings.models import Finding, Recommendation
from backend.app.compliance.findings.severity import Severity, SeverityLevel
from backend.app.inventory.dto import InventorySnapshot as NetBoxInventorySnapshot
from backend.app.snapshot.entities import InventorySnapshot as LiveInventorySnapshot


@dataclass(slots=True)
class ComparisonEngine:
    """Compare canonical NetBox inventory against live inventory snapshots."""

    matcher: InventoryMatcher = field(default_factory=InventoryMatcher)
    identity_comparator: IdentityComparator = field(default_factory=IdentityComparator)
    device_comparator: DeviceComparator = field(default_factory=DeviceComparator)
    interface_comparator: InterfaceComparator = field(
        default_factory=InterfaceComparator
    )
    vlan_comparator: VLANComparator = field(default_factory=VLANComparator)
    neighbor_comparator: NeighborComparator = field(default_factory=NeighborComparator)
    platform_comparator: PlatformComparator = field(default_factory=PlatformComparator)
    evidence_generator: EvidenceGenerator = field(default_factory=EvidenceGenerator)
    difference_filter: DifferenceFilter | None = None

    def compare(
        self,
        netbox: NetBoxInventorySnapshot,
        live: LiveInventorySnapshot,
    ) -> InventoryComparisonResult:
        """Run the full comparison pipeline."""

        match = self.matcher.match(netbox, live)
        registry = DifferenceRegistry()
        registry.extend(self.identity_comparator.compare(match))
        registry.extend(self.device_comparator.compare(match))
        registry.extend(self.interface_comparator.compare(match))
        registry.extend(self.vlan_comparator.compare(netbox, live))
        registry.extend(self.neighbor_comparator.compare(live))
        registry.extend(self.platform_comparator.compare(match))

        differences = registry.all()
        if self.difference_filter is not None:
            differences = self.difference_filter.apply(differences)
        findings = tuple(self._finding_from_difference(item) for item in differences)
        metrics = ComparisonMetrics.from_differences(differences, findings)
        return InventoryComparisonResult(
            differences=differences,
            findings=findings,
            metrics=metrics,
        )

    def _finding_from_difference(self, difference: Difference) -> Finding:
        severity = self._severity(difference.difference_type)
        evidence = self.evidence_generator.from_difference(difference)
        return Finding.create(
            uuid5(NAMESPACE_URL, f"nop-comparison:{difference.difference_type.value}"),
            self._title(difference),
            severity,
            description=difference.description,
            evidence=(evidence,),
            recommendation=Recommendation(
                summary="Review NetBox source-of-truth and live device state.",
                rationale=(
                    "Inventory drift must be reconciled before compliance scoring."
                ),
                steps=(
                    "Confirm NetBox inventory is authoritative.",
                    "Validate live device inventory.",
                    "Plan an approved correction outside this application.",
                ),
            ),
            observed_state={
                "value": difference.observed,
                "difference_type": difference.difference_type.value,
            },
            expected_state={"value": difference.expected},
        )

    @staticmethod
    def _severity(difference_type: DifferenceType) -> Severity:
        if difference_type in {DifferenceType.MISSING, DifferenceType.CONFLICT}:
            return Severity(SeverityLevel.HIGH, score=80, label="High")
        if difference_type in {DifferenceType.UNEXPECTED, DifferenceType.MODIFIED}:
            return Severity(SeverityLevel.MEDIUM, score=50, label="Medium")
        if difference_type == DifferenceType.DUPLICATE:
            return Severity(SeverityLevel.HIGH, score=75, label="High")
        return Severity(SeverityLevel.INFO, score=10, label="Info")

    @staticmethod
    def _title(difference: Difference) -> str:
        return (
            f"{difference.difference_type.value.title()} "
            f"{difference.subject_type} drift: {difference.subject_id}"
        )
