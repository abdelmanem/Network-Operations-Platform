"""Reporting application service."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.config.settings import get_settings
from backend.app.orchestration.results import OrchestrationResult
from backend.app.reporting.context import DiscoveryRunSnapshot, ReportContext
from backend.app.reporting.engine import ReportEngine
from backend.app.reporting.enums import ExportFormat, ReportType
from backend.app.reporting.models import ExportResult, RenderedDocument, ReportData
from backend.app.services.base import BaseService, ServiceContext


@dataclass(slots=True)
class ReportService(BaseService):
    """High-level reporting service for cached orchestration results."""

    context: ServiceContext = field(
        default_factory=lambda: ServiceContext(settings=get_settings())
    )
    engine: ReportEngine = field(default_factory=ReportEngine)

    def context_from_orchestration(
        self,
        result: OrchestrationResult,
        *,
        discovery_run: DiscoveryRunSnapshot | None = None,
    ) -> ReportContext:
        """Build report context from a cached orchestration result."""

        return ReportContext(
            netbox_inventory=result.netbox_inventory,
            live_snapshot=result.live_snapshot,
            comparison_result=result.comparison_result,
            evaluation_decision=result.evaluation_decision,
            discovery_run=discovery_run,
            run_id=result.run_id,
            job_id=result.job_id,
        )

    def build_report(
        self,
        report_type: ReportType,
        context: ReportContext,
    ) -> ReportData:
        """Build report data without exporting."""

        return self.engine.build(report_type, context)

    def render_report(self, report_data: ReportData) -> RenderedDocument:
        """Render report data."""

        return self.engine.render(report_data)

    def export_report(
        self,
        document: RenderedDocument,
        export_format: ExportFormat,
    ) -> ExportResult:
        """Export a rendered report."""

        return self.engine.export(document, export_format)

    def generate_report(
        self,
        report_type: ReportType,
        context: ReportContext,
        export_format: ExportFormat,
    ) -> ExportResult:
        """Generate and export a report from cached context."""

        self.logger.info(
            "Generating report",
            extra={
                "report_type": report_type.value,
                "export_format": export_format.value,
                "run_id": str(context.run_id) if context.run_id else None,
            },
        )
        return self.engine.generate(report_type, context, export_format)
