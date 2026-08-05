"""Difference registry and builder utilities."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.comparison.diff import Difference, DifferenceType


@dataclass(slots=True)
class DifferenceRegistry:
    """Collect unique inventory differences."""

    _differences: dict[str, Difference] = field(default_factory=dict)

    def add(self, difference: Difference) -> None:
        """Add or replace a difference by stable key."""

        self._differences[difference.key] = difference

    def extend(self, differences: tuple[Difference, ...]) -> None:
        """Add multiple differences."""

        for difference in differences:
            self.add(difference)

    def all(self) -> tuple[Difference, ...]:
        """Return all registered differences."""

        return tuple(self._differences.values())

    def by_type(self, difference_type: DifferenceType) -> tuple[Difference, ...]:
        """Return differences of one type."""

        return tuple(
            difference
            for difference in self._differences.values()
            if difference.difference_type == difference_type
        )

    def clear(self) -> None:
        """Clear all differences."""

        self._differences.clear()


@dataclass(slots=True)
class DifferenceBuilder:
    """Factory for common inventory differences."""

    def missing(
        self,
        subject_type: str,
        subject_id: str,
        *,
        expected: object,
        description: str,
    ) -> Difference:
        """Create a missing live-object difference."""

        return Difference.create(
            DifferenceType.MISSING,
            subject_type,
            subject_id,
            expected=expected,
            description=description,
        )

    def unexpected(
        self,
        subject_type: str,
        subject_id: str,
        *,
        observed: object,
        description: str,
    ) -> Difference:
        """Create an unexpected live-object difference."""

        return Difference.create(
            DifferenceType.UNEXPECTED,
            subject_type,
            subject_id,
            observed=observed,
            description=description,
        )

    def modified(
        self,
        subject_type: str,
        subject_id: str,
        field_name: str,
        *,
        expected: object,
        observed: object,
    ) -> Difference:
        """Create a modified field difference."""

        return Difference.create(
            DifferenceType.MODIFIED,
            subject_type,
            subject_id,
            field_name=field_name,
            expected=expected,
            observed=observed,
            description=f"{subject_type} {subject_id} field {field_name} differs.",
        )

    def duplicate(
        self,
        subject_type: str,
        subject_id: str,
        *,
        observed: object,
        description: str,
    ) -> Difference:
        """Create a duplicate identity difference."""

        return Difference.create(
            DifferenceType.DUPLICATE,
            subject_type,
            subject_id,
            observed=observed,
            description=description,
        )

    def unsupported(
        self,
        subject_type: str,
        subject_id: str,
        *,
        observed: object,
        description: str,
    ) -> Difference:
        """Create an unsupported comparison difference."""

        return Difference.create(
            DifferenceType.UNSUPPORTED,
            subject_type,
            subject_id,
            observed=observed,
            description=description,
        )
