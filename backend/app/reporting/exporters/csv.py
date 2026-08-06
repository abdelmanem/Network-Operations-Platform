"""CSV report exporter."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Protocol

from backend.app.reporting.enums import DocumentNodeType, ExportFormat
from backend.app.reporting.models import DocumentNode, ExportResult, RenderedDocument


class SupportsWriter(Protocol):
    """Minimal CSV writer protocol for typed helpers."""

    def writerow(self, row: list[object]) -> None:
        """Write a CSV row."""


@dataclass(frozen=True, slots=True)
class CsvExporter:
    """Export rendered documents as CSV."""

    format: ExportFormat = ExportFormat.CSV

    def export(self, document: RenderedDocument) -> ExportResult:
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["section", "key", "value"])
        _write_statistics(writer, document)
        _write_nodes(writer, document.root, section="document")
        filename = f"{document.report_type.value}.csv"
        return ExportResult(
            format=self.format,
            content=buffer.getvalue().encode("utf-8"),
            mime_type="text/csv",
            filename=filename,
        )


def _write_statistics(writer: SupportsWriter, document: RenderedDocument) -> None:
    stats = document.statistics
    for key, value in {
        "total_devices": stats.total_devices,
        "reachable_devices": stats.reachable_devices,
        "unreachable_devices": stats.unreachable_devices,
        "discovery_success_pct": stats.discovery_success_pct,
        "netbox_accuracy_pct": stats.netbox_accuracy_pct,
        "compliance_score": stats.compliance_score,
        "critical_findings": stats.critical_findings,
        "major_findings": stats.major_findings,
        "minor_findings": stats.minor_findings,
        "missing_devices": stats.missing_devices,
        "extra_devices": stats.extra_devices,
        "changed_devices": stats.changed_devices,
        "interface_changes": stats.interface_changes,
        "vlan_changes": stats.vlan_changes,
        "configuration_changes": stats.configuration_changes,
    }.items():
        writer.writerow(["statistics", key, value])


def _write_nodes(
    writer: SupportsWriter,
    node: DocumentNode,
    *,
    section: str,
) -> None:
    if node.node_type == DocumentNodeType.SECTION:
        section = str(node.attributes.get("title", section))

    if node.node_type == DocumentNodeType.METRIC:
        writer.writerow(
            [
                section,
                node.attributes.get("key"),
                node.attributes.get("value"),
            ]
        )
    elif node.node_type == DocumentNodeType.KEY_VALUE and "value" in node.attributes:
        writer.writerow(
            [
                section,
                node.attributes.get("key"),
                node.attributes.get("value"),
            ]
        )
    elif node.node_type == DocumentNodeType.TABLE:
        headers = node.attributes.get("headers", ())
        rows = node.attributes.get("rows", ())
        if isinstance(headers, tuple) and isinstance(rows, tuple):
            for row in rows:
                if isinstance(row, tuple):
                    for header, cell in zip(headers, row, strict=False):
                        writer.writerow([section, header, cell])

    for child in node.children:
        _write_nodes(writer, child, section=section)
