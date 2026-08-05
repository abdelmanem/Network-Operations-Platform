"""Comparison filtering helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.comparison.diff import Difference, DifferenceType


@dataclass(frozen=True, slots=True)
class DifferenceFilter:
    """Filter differences by type and subject type."""

    include_types: frozenset[DifferenceType] = field(default_factory=frozenset)
    exclude_types: frozenset[DifferenceType] = field(default_factory=frozenset)
    subject_types: frozenset[str] = field(default_factory=frozenset)

    def apply(self, differences: tuple[Difference, ...]) -> tuple[Difference, ...]:
        """Return differences accepted by this filter."""

        accepted: list[Difference] = []
        for difference in differences:
            if (
                self.include_types
                and difference.difference_type not in self.include_types
            ):
                continue
            if difference.difference_type in self.exclude_types:
                continue
            if self.subject_types and difference.subject_type not in self.subject_types:
                continue
            accepted.append(difference)
        return tuple(accepted)
