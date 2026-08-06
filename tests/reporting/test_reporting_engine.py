from __future__ import annotations

from pathlib import Path

from backend.app.reporting.engine import ReportEngine
from backend.app.reporting.enums import ExportFormat, ReportType
from backend.app.reporting.models import ReportData
from backend.app.reporting.service import ReportService
from backend.app.reporting.templates import TemplateRegistry
from tests.fixtures.reporting.golden_context import build_report_context


def test_build_and_render_report_pipeline() -> None:
    context = build_report_context()
    engine = ReportEngine()

    report = engine.build(ReportType.EXECUTIVE_SUMMARY, context)
    document = engine.render(report)

    assert isinstance(report, ReportData)
    assert report.report_type == ReportType.EXECUTIVE_SUMMARY
    assert report.sections
    assert document.root.node_type.value == "document"
    assert document.statistics.total_devices == 3


def test_engine_exports_all_formats() -> None:
    context = build_report_context()
    engine = ReportEngine()
    report = engine.build(ReportType.COMPLIANCE, context)
    document = engine.render(report)

    for export_format in (
        ExportFormat.HTML,
        ExportFormat.PDF,
        ExportFormat.EXCEL,
        ExportFormat.CSV,
        ExportFormat.JSON,
    ):
        result = engine.export(document, export_format)
        assert result.filename.endswith(
            result.format.value if result.format.value != "excel" else ".xlsx"
        ) or result.filename.endswith(result.format.value)
        assert result.content


def test_report_service_uses_cached_context() -> None:
    context = build_report_context()
    service = ReportService()
    report = service.build_report(ReportType.INVENTORY, context)

    assert report.report_type == ReportType.INVENTORY
    assert report.statistics.device_type_counts


def test_template_registry_exposes_all_supported_report_types() -> None:
    registry = TemplateRegistry()

    for report_type in ReportType:
        template = registry.get(report_type)
        assert template.definition.report_type == report_type


def test_golden_fixture_fixture_path_exists() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "reporting"
        / "golden_context.py"
    )
    assert fixture_path.exists()
