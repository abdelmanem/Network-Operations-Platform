"""Structured report summary generation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from backend.app.reporting.context import ReportContext
from backend.app.reporting.statistics import ReportStatistics


@dataclass(frozen=True, slots=True)
class ReportSummary:
    """Structured executive summary data."""

    headline: str
    highlights: tuple[str, ...]
    metrics: Mapping[str, object]


class SummaryGenerator:
    """Build structured summary payloads from cached statistics."""

    def generate(
        self,
        context: ReportContext,
        statistics: ReportStatistics,
    ) -> ReportSummary:
        """Return structured summary data without prose templates."""

        highlights = self._build_highlights(statistics)
        metrics = MappingProxyType(
            {
                "total_devices": statistics.total_devices,
                "compliance_score": statistics.compliance_score,
                "netbox_accuracy_pct": statistics.netbox_accuracy_pct,
                "discovery_success_pct": statistics.discovery_success_pct,
                "critical_findings": statistics.critical_findings,
                "missing_devices": statistics.missing_devices,
                "extra_devices": statistics.extra_devices,
            }
        )
        headline = self._headline(statistics)
        return ReportSummary(headline=headline, highlights=highlights, metrics=metrics)

    def _headline(self, statistics: ReportStatistics) -> str:
        return (
            f"compliance_score:{statistics.compliance_score}|"
            f"netbox_accuracy:{statistics.netbox_accuracy_pct}|"
            f"devices:{statistics.total_devices}"
        )

    def _build_highlights(self, statistics: ReportStatistics) -> tuple[str, ...]:
        items = [
            f"total_devices:{statistics.total_devices}",
            f"reachable_devices:{statistics.reachable_devices}",
            f"unreachable_devices:{statistics.unreachable_devices}",
            f"discovery_success_pct:{statistics.discovery_success_pct}",
            f"netbox_accuracy_pct:{statistics.netbox_accuracy_pct}",
            f"compliance_score:{statistics.compliance_score}",
            f"critical_findings:{statistics.critical_findings}",
            f"major_findings:{statistics.major_findings}",
            f"minor_findings:{statistics.minor_findings}",
            f"missing_devices:{statistics.missing_devices}",
            f"extra_devices:{statistics.extra_devices}",
            f"changed_devices:{statistics.changed_devices}",
        ]
        return tuple(items)
