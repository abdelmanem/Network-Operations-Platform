"""NetBox-to-live inventory comparison engine."""

from backend.app.comparison.comparator import (
    DeviceComparator,
    IdentityComparator,
    InterfaceComparator,
    NeighborComparator,
    PlatformComparator,
    VLANComparator,
)
from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.comparison.engine import ComparisonEngine
from backend.app.comparison.evidence import EvidenceGenerator
from backend.app.comparison.filters import DifferenceFilter
from backend.app.comparison.matcher import InventoryMatch, InventoryMatcher
from backend.app.comparison.registry import DifferenceBuilder, DifferenceRegistry
from backend.app.comparison.result import ComparisonMetrics, InventoryComparisonResult

__all__ = [
    "ComparisonEngine",
    "ComparisonMetrics",
    "DeviceComparator",
    "Difference",
    "DifferenceBuilder",
    "DifferenceFilter",
    "DifferenceRegistry",
    "DifferenceType",
    "EvidenceGenerator",
    "IdentityComparator",
    "InterfaceComparator",
    "InventoryComparisonResult",
    "InventoryMatch",
    "InventoryMatcher",
    "NeighborComparator",
    "PlatformComparator",
    "VLANComparator",
]
