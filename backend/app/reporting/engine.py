"""Reporting engine orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.reporting.builder import ReportBuilder
from backend.app.reporting.context import ReportContext
from backend.app.reporting.enums import ExportFormat, ReportType
from backend.app.reporting.exporters import ExporterRegistry
from backend.app.reporting.exporters.csv import CsvExporter
from backend.app.reporting.exporters.excel import ExcelExporter
from backend.app.reporting.exporters.html import HtmlExporter
from backend.app.reporting.exporters.json import JsonExporter
from backend.app.reporting.exporters.pdf import PdfExporter
from backend.app.reporting.models import ExportResult, RenderedDocument, ReportData
from backend.app.reporting.renderer import ReportRenderer


def _default_exporters() -> ExporterRegistry:
    registry = ExporterRegistry()
    registry.register(HtmlExporter())
    registry.register(PdfExporter())
    registry.register(ExcelExporter())
    registry.register(CsvExporter())
    registry.register(JsonExporter())
    return registry


@dataclass(slots=True)
class ReportEngine:
    """Orchestrate build, render, and export without format-specific builder logic."""

    builder: ReportBuilder = field(default_factory=ReportBuilder)
    renderer: ReportRenderer = field(default_factory=ReportRenderer)
    exporters: ExporterRegistry = field(default_factory=_default_exporters)

    def build(self, report_type: ReportType, context: ReportContext) -> ReportData:
        """Build immutable report data from cached context."""

        return self.builder.build(report_type, context)

    def render(self, report_data: ReportData) -> RenderedDocument:
        """Render report data using a pluggable template."""

        return self.renderer.render(report_data)

    def export(
        self,
        document: RenderedDocument,
        export_format: ExportFormat,
    ) -> ExportResult:
        """Export a rendered document using a registered exporter."""

        exporter = self.exporters.get(export_format)
        return exporter.export(document)

    def generate(
        self,
        report_type: ReportType,
        context: ReportContext,
        export_format: ExportFormat,
    ) -> ExportResult:
        """Build, render, and export a report in one call."""

        report_data = self.build(report_type, context)
        document = self.render(report_data)
        return self.export(document, export_format)
