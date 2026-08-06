from __future__ import annotations

from backend.app.reporting.engine import ReportEngine
from backend.app.reporting.enums import ExportFormat, ReportType
from backend.app.reporting.exporters.csv import CsvExporter
from backend.app.reporting.exporters.excel import ExcelExporter
from backend.app.reporting.exporters.html import HtmlExporter
from backend.app.reporting.exporters.json import JsonExporter
from backend.app.reporting.exporters.pdf import PdfExporter
from tests.fixtures.reporting.golden_context import build_report_context


def test_exporters_return_expected_formats() -> None:
    context = build_report_context()
    engine = ReportEngine()
    document = engine.render(engine.build(ReportType.TECHNICAL, context))

    assert HtmlExporter().export(document).format == ExportFormat.HTML
    assert CsvExporter().export(document).format == ExportFormat.CSV
    assert JsonExporter().export(document).format == ExportFormat.JSON
    assert ExcelExporter().export(document).format == ExportFormat.EXCEL
    assert PdfExporter().export(document).format == ExportFormat.PDF
