from __future__ import annotations

from backend.app.comparison import DifferenceBuilder, DifferenceRegistry, DifferenceType


def test_difference_registry_deduplicates_by_stable_key() -> None:
    builder = DifferenceBuilder()
    first = builder.modified(
        "device",
        "switch-01",
        "serial",
        expected="A",
        observed="B",
    )
    second = builder.modified(
        "device",
        "switch-01",
        "serial",
        expected="A",
        observed="C",
    )
    registry = DifferenceRegistry()

    registry.add(first)
    registry.add(second)

    assert registry.all() == (second,)
    assert registry.by_type(DifferenceType.MODIFIED) == (second,)
