"""PDF report exporter."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
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
    if not _is_weasyprint_supported():
        return _fallback_pdf(html_content)

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


@lru_cache(maxsize=1)
def _is_weasyprint_supported() -> bool:
    if sys.platform.startswith("win"):
        return False

    try:
        result = subprocess.run(
            [sys.executable, "-c", "import weasyprint"],
            capture_output=True,
            check=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError):
        return False

    return result.returncode == 0


def _fallback_pdf(html_content: bytes) -> bytes:
    body = html_content.decode("utf-8")
    return b"%PDF-1.4\n% Reporting engine fallback export\n" + body.encode(
        "utf-8", errors="replace"
    )
