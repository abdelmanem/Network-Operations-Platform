"""Discrepancies section builder."""

from __future__ import annotations

from types import MappingProxyType

from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import SectionType
from backend.app.reporting.models import ReportSection
from backend.app.reporting.statistics import ReportStatistics


def build_discrepancies_section(
    context: ReportContext,
    statistics: ReportStatistics,
) -> ReportSection:
    """Build structured discrepancy section data."""

    differences: tuple[dict[str, object], ...] = ()
    if context.comparison_result is not None:
        differences = tuple(
            {
                "difference_type": difference.difference_type.value,
                "subject_type": difference.subject_type,
                "subject_id": difference.subject_id,
                "field_name": difference.field_name,
                "expected": difference.expected,
                "observed": difference.observed,
                "description": difference.description,
                "key": difference.key,
            }
            for difference in context.comparison_result.differences
        )

    return ReportSection(
        section_type=SectionType.DISCREPANCIES,
        title="section.discrepancies",
        data=MappingProxyType(
            {
                "differences": differences,
                "missing_devices": statistics.missing_devices,
                "extra_devices": statistics.extra_devices,
                "changed_devices": statistics.changed_devices,
                "interface_changes": statistics.interface_changes,
                "vlan_changes": statistics.vlan_changes,
                "configuration_changes": statistics.configuration_changes,
            }
        ),
    )
