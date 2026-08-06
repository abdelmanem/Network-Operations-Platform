"""Metrics section builder."""

from __future__ import annotations

from types import MappingProxyType

from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import SectionType
from backend.app.reporting.models import ReportSection
from backend.app.reporting.statistics import ReportStatistics


def build_metrics_section(
    context: ReportContext,
    statistics: ReportStatistics,
) -> ReportSection:
    """Build structured metrics section data."""

    discovery = None
    if context.discovery_run is not None:
        run = context.discovery_run
        discovery = {
            "run_id": str(run.run_id),
            "total_targets": run.total_targets,
            "successful_targets": run.successful_targets,
            "failed_targets": run.failed_targets,
            "skipped_targets": run.skipped_targets,
            "started_at": run.started_at.isoformat(),
            "finished_at": (
                run.finished_at.isoformat() if run.finished_at is not None else None
            ),
        }

    historical = tuple(
        {
            "run_id": str(entry.run_id),
            "captured_at": entry.captured_at.isoformat(),
            "total_devices": entry.total_devices,
            "missing_devices": entry.missing_devices,
            "extra_devices": entry.extra_devices,
            "changed_devices": entry.changed_devices,
            "compliance_score": entry.compliance_score,
            "critical_findings": entry.critical_findings,
            "major_findings": entry.major_findings,
            "minor_findings": entry.minor_findings,
        }
        for entry in context.historical_runs
    )

    return ReportSection(
        section_type=SectionType.METRICS,
        title="section.metrics",
        data=MappingProxyType(
            {
                "statistics": {
                    "total_devices": statistics.total_devices,
                    "reachable_devices": statistics.reachable_devices,
                    "unreachable_devices": statistics.unreachable_devices,
                    "discovery_success_pct": statistics.discovery_success_pct,
                    "netbox_accuracy_pct": statistics.netbox_accuracy_pct,
                    "compliance_score": statistics.compliance_score,
                    "critical_findings": statistics.critical_findings,
                    "major_findings": statistics.major_findings,
                    "minor_findings": statistics.minor_findings,
                    "missing_devices": statistics.missing_devices,
                    "extra_devices": statistics.extra_devices,
                    "changed_devices": statistics.changed_devices,
                    "interface_changes": statistics.interface_changes,
                    "vlan_changes": statistics.vlan_changes,
                    "configuration_changes": statistics.configuration_changes,
                },
                "discovery": discovery,
                "historical_runs": historical,
            }
        ),
    )
