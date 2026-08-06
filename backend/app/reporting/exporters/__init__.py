"""Report exporter protocol and registry."""

from __future__ import annotations

from typing import Protocol

from backend.app.reporting.enums import ExportFormat
from backend.app.reporting.models import ExportResult, RenderedDocument


class ReportExporter(Protocol):
    """Protocol for report exporters."""

    @property
    def format(self) -> ExportFormat:
        """Return the exporter format."""

    def export(self, document: RenderedDocument) -> ExportResult:
        """Export a rendered document."""


class ExporterRegistry:
    """Registry of pluggable report exporters."""

    def __init__(self) -> None:
        self._exporters: dict[ExportFormat, ReportExporter] = {}

    def register(self, exporter: ReportExporter) -> None:
        """Register an exporter."""

        self._exporters[exporter.format] = exporter

    def get(self, export_format: ExportFormat) -> ReportExporter:
        """Return an exporter for the requested format."""

        exporter = self._exporters.get(export_format)
        if exporter is None:
            msg = f"No exporter registered for format {export_format.value}"
            raise KeyError(msg)
        return exporter

    @property
    def formats(self) -> tuple[ExportFormat, ...]:
        """Return registered export formats."""

        return tuple(self._exporters.keys())
