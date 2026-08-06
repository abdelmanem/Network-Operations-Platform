"""Statistical aggregations for historical analytics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from backend.app.analytics.context import HistoricalFindingEntry, HistoricalRunEntry
from backend.app.analytics.metadata import AnalyticsStatistics


def calculate_statistics(
    runs: Iterable[HistoricalRunEntry],
    findings: Iterable[HistoricalFindingEntry],
) -> AnalyticsStatistics:
    """Calculate core historical statistics."""

    run_list = tuple(runs)
    finding_list = tuple(findings)
    if not run_list:
        return AnalyticsStatistics(
            device_growth=0,
            vendor_distribution={},
            platform_distribution={},
            discovery_success_trend=0.0,
            compliance_trend=0.0,
            inventory_trend=0.0,
            findings_trend=0.0,
            risk_trend=0.0,
        )

    latest = run_list[-1]
    earliest = run_list[0]
    device_growth = latest.total_devices - earliest.total_devices
    vendor_distribution = Counter({"default": len(run_list)})
    platform_distribution = Counter({"default": len(run_list)})
    discovery_success_trend = float(
        latest.successful_targets / latest.total_targets
        if latest.total_targets
        else 0.0
    )
    compliance_trend = float(latest.compliance_score) - float(earliest.compliance_score)
    inventory_trend = latest.discovered_devices - earliest.discovered_devices
    findings_trend = len(finding_list)
    risk_trend = float(latest.risk_score or 0.0) - float(earliest.risk_score or 0.0)

    return AnalyticsStatistics(
        device_growth=device_growth,
        vendor_distribution=dict(vendor_distribution),
        platform_distribution=dict(platform_distribution),
        discovery_success_trend=discovery_success_trend,
        compliance_trend=compliance_trend,
        inventory_trend=inventory_trend,
        findings_trend=findings_trend,
        risk_trend=risk_trend,
    )
