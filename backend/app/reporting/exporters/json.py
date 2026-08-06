"""JSON report exporter."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.reporting.enums import ExportFormat
from backend.app.reporting.exporters._serialization import document_to_json
from backend.app.reporting.models import ExportResult, RenderedDocument


@dataclass(frozen=True, slots=True)
class JsonExporter:
    """Export rendered documents as JSON."""

    format: ExportFormat = ExportFormat.JSON

    def export(self, document: RenderedDocument) -> ExportResult:
        content = document_to_json(document)
        filename = f"{document.report_type.value}.json"
        return ExportResult(
            format=self.format,
            content=content,
            mime_type="application/json",
            filename=filename,
        )
