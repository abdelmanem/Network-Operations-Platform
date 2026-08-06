"""Structured report renderer."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.reporting.enums import DocumentNodeType, SectionType
from backend.app.reporting.models import (
    DocumentNode,
    RenderedDocument,
    ReportData,
    ReportSection,
)
from backend.app.reporting.statistics import ReportStatistics
from backend.app.reporting.templates import ReportTemplate, TemplateRegistry


class ReportRenderer:
    """Render report data into a structured document tree."""

    def __init__(self, *, template_registry: TemplateRegistry | None = None) -> None:
        self._template_registry = template_registry or TemplateRegistry()

    def render(self, report_data: ReportData) -> RenderedDocument:
        """Apply a template to report data."""

        template = self._template_registry.get(report_data.report_type)
        section_nodes = tuple(
            self._render_section(section, template) for section in report_data.sections
        )
        root = DocumentNode(
            node_type=DocumentNodeType.DOCUMENT,
            attributes={
                "title": report_data.metadata.title,
                "report_type": report_data.report_type.value,
            },
            children=(
                DocumentNode(
                    node_type=DocumentNodeType.SECTION,
                    attributes={"title": "section.statistics"},
                    children=self._render_statistics(report_data.statistics),
                ),
                *section_nodes,
            ),
        )
        return RenderedDocument(
            report_type=report_data.report_type,
            metadata=report_data.metadata,
            root=root,
            statistics=report_data.statistics,
            recommendations=report_data.recommendations,
        )

    def _render_section(
        self,
        section: ReportSection,
        template: ReportTemplate,
    ) -> DocumentNode:
        title = template.section_title(section.section_type)
        children = self._render_section_data(section.section_type, section.data)
        return DocumentNode(
            node_type=DocumentNodeType.SECTION,
            attributes={"title": title, "section_type": section.section_type.value},
            children=children,
        )

    def _render_section_data(
        self,
        section_type: SectionType,
        data: Mapping[str, object],
    ) -> tuple[DocumentNode, ...]:
        if section_type == SectionType.EXECUTIVE_SUMMARY:
            return self._render_key_values(data)
        if section_type in {
            SectionType.INVENTORY,
            SectionType.COMPLIANCE,
            SectionType.FINDINGS,
            SectionType.DISCREPANCIES,
            SectionType.RECOMMENDATIONS,
            SectionType.METRICS,
            SectionType.APPENDIX,
        }:
            return self._render_structured_payload(data)
        return self._render_key_values(data)

    def _render_statistics(
        self,
        statistics: ReportStatistics,
    ) -> tuple[DocumentNode, ...]:
        metrics = {
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
        }
        return tuple(
            DocumentNode(
                node_type=DocumentNodeType.METRIC,
                attributes={"key": key, "value": value},
            )
            for key, value in metrics.items()
        )

    def _render_key_values(
        self,
        data: Mapping[str, object],
    ) -> tuple[DocumentNode, ...]:
        nodes: list[DocumentNode] = []
        for key, value in data.items():
            if isinstance(value, (list, tuple, dict)):
                nodes.append(
                    DocumentNode(
                        node_type=DocumentNodeType.KEY_VALUE,
                        attributes={"key": key},
                        children=self._render_nested(value),
                    )
                )
            else:
                nodes.append(
                    DocumentNode(
                        node_type=DocumentNodeType.KEY_VALUE,
                        attributes={"key": key, "value": value},
                    )
                )
        return tuple(nodes)

    def _render_structured_payload(
        self,
        data: Mapping[str, object],
    ) -> tuple[DocumentNode, ...]:
        nodes: list[DocumentNode] = []
        for key, value in data.items():
            if isinstance(value, list | tuple):
                rows = [self._serialize_row(item) for item in value]
                if rows and all(isinstance(row, dict) for row in rows):
                    headers = tuple(rows[0].keys()) if rows else ()
                    table_rows = tuple(
                        tuple(row[col] for col in headers) for row in rows
                    )
                    nodes.append(
                        DocumentNode(
                            node_type=DocumentNodeType.TABLE,
                            attributes={
                                "key": key,
                                "headers": headers,
                                "rows": table_rows,
                            },
                        )
                    )
                else:
                    nodes.append(
                        DocumentNode(
                            node_type=DocumentNodeType.LIST,
                            attributes={"key": key, "items": tuple(value)},
                        )
                    )
            elif isinstance(value, dict):
                nodes.append(
                    DocumentNode(
                        node_type=DocumentNodeType.KEY_VALUE,
                        attributes={"key": key},
                        children=self._render_key_values(value),
                    )
                )
            else:
                nodes.append(
                    DocumentNode(
                        node_type=DocumentNodeType.KEY_VALUE,
                        attributes={"key": key, "value": value},
                    )
                )
        return tuple(nodes)

    def _render_nested(self, value: object) -> tuple[DocumentNode, ...]:
        if isinstance(value, Mapping):
            return self._render_key_values(value)
        if isinstance(value, list | tuple):
            return (
                DocumentNode(
                    node_type=DocumentNodeType.LIST,
                    attributes={"items": tuple(value)},
                ),
            )
        return (
            DocumentNode(
                node_type=DocumentNodeType.PARAGRAPH,
                attributes={"text": str(value)},
            ),
        )

    @staticmethod
    def _serialize_row(item: object) -> dict[str, Any]:
        if isinstance(item, Mapping):
            return {str(key): value for key, value in item.items()}
        return {"value": item}
