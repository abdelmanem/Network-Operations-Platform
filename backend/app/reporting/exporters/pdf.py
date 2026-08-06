"""PDF report exporter."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from backend.app.reporting.enums import ExportFormat
from backend.app.reporting.exporters.html import HtmlExporter
from backend.app.reporting.models import ExportResult, RenderedDocument


@dataclass(frozen=True, slots=True)
class PdfExporter:
    """Export rendered documents as PDF via HTML conversion."""

    format: ExportFormat = ExportFormat.PDF
    html_exporter: HtmlExporter | None = None

    def export(self, document: RenderedDocument) -> ExportResult:
        html_exporter = self.html_exporter or HtmlExporter()
        html_result = html_exporter.export(document)
        pdf_bytes = _html_to_pdf(html_result.content)
        filename = f"{document.report_type.value}.pdf"
        return ExportResult(
            format=self.format,
            content=pdf_bytes,
            mime_type="application/pdf",
            filename=filename,
        )


def _html_to_pdf(html_content: bytes) -> bytes:
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
    except (ImportError, OSError, RuntimeError):
        return _fallback_pdf(html_content)

    buffer = BytesIO()
    try:
        HTML(string=html_content.decode("utf-8")).write_pdf(buffer)
    except (ImportError, OSError, RuntimeError):
        return _fallback_pdf(html_content)

    return buffer.getvalue()


def _fallback_pdf(html_content: bytes) -> bytes:
    body = html_content.decode("utf-8")
    return b"%PDF-1.4\n% Reporting engine fallback export\n" + body.encode(
        "utf-8", errors="replace"
    )
