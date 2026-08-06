from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.comparison.diff import Difference, DifferenceType
from backend.app.comparison.result import ComparisonMetrics, InventoryComparisonResult
from backend.app.compliance.findings.evidence import Evidence
from backend.app.compliance.findings.models import Finding
from backend.app.compliance.findings.severity import Severity, SeverityLevel
from backend.app.evaluation.context import (
    EvaluationDecision,
    EvaluationMetrics,
    EvaluationStatus,
)
from backend.app.inventory.dto import InventorySnapshot
from backend.app.reporting.context import (
    DiscoveryRunSnapshot,
    HistoricalRunSnapshot,
    ReportContext,
)
from backend.app.snapshot.entities import DeviceSnapshot
from backend.app.snapshot.entities import InventorySnapshot as LiveInventorySnapshot


def build_report_context() -> ReportContext:
    netbox_inventory = InventorySnapshot(
        devices=(
            _device("r1", "router", "Cisco", "C9300", "iosxe"),
            _device("r2", "router", "Juniper", "MX", "junos"),
            _device("r3", "switch", "Arista", "DCS-7050", "eos"),
        )
    )
    live_snapshot = LiveInventorySnapshot(
        devices=(
            DeviceSnapshot(
                device_id="r1",
                name="r1",
                manufacturer="Cisco",
                model="C9300",
                platform="iosxe",
            ),
            DeviceSnapshot(
                device_id="r2",
                name="r2",
                manufacturer="Juniper",
                model="MX",
                platform="junos",
            ),
            DeviceSnapshot(
                device_id="r4",
                name="r4",
                manufacturer="Nokia",
                model="7750",
                platform="sros",
            ),
        )
    )
    comparison = InventoryComparisonResult(
        differences=(
            Difference(
                difference_type=DifferenceType.MISSING,
                subject_type="device",
                subject_id="r3",
                field_name="presence",
                expected="present",
                observed="missing",
                description="Device missing from live inventory",
            ),
            Difference(
                difference_type=DifferenceType.MODIFIED,
                subject_type="interface",
                subject_id="Gig0/0",
                field_name="oper_status",
                expected="up",
                observed="down",
                description="Interface changed",
            ),
        ),
        findings=(
            Finding(
                id=uuid4(),
                rule_id=uuid4(),
                title="Missing device rule",
                severity=Severity(level=SeverityLevel.CRITICAL, score=100),
                description="Device missing from inventory",
                evidence=(
                    Evidence(
                        id=uuid4(),
                        source="comparison",
                        description="Device is missing",
                        reference="r3",
                    ),
                ),
            ),
        ),
        metrics=ComparisonMetrics(
            total_differences=2, total_findings=1, missing=1, unexpected=0, modified=1
        ),
    )
    evaluation = EvaluationDecision(
        status=EvaluationStatus.NON_COMPLIANT,
        risk_score=75,
        compliance_score=65,
        metrics=EvaluationMetrics(
            total_rules=4,
            evaluated_rules=4,
            compliant=1,
            non_compliant=3,
            waived=0,
            not_applicable=0,
            errors=0,
            risk_score=75,
            compliance_score=65,
        ),
        evidence=(
            Evidence(
                id=uuid4(),
                source="evaluation",
                description="Compliance failure evidence",
                reference="rule.1",
            ),
        ),
        rule_results=(),
    )
    discovery = DiscoveryRunSnapshot(
        run_id=uuid4(),
        total_targets=5,
        successful_targets=4,
        failed_targets=1,
        skipped_targets=0,
        started_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        finished_at=datetime(2026, 8, 1, 10, 5, tzinfo=UTC),
    )
    historical = HistoricalRunSnapshot(
        run_id=uuid4(),
        captured_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        total_devices=3,
        missing_devices=1,
        extra_devices=1,
        changed_devices=1,
        compliance_score=65,
        critical_findings=1,
        major_findings=0,
        minor_findings=0,
    )
    return ReportContext(
        netbox_inventory=netbox_inventory,
        live_snapshot=live_snapshot,
        comparison_result=comparison,
        evaluation_decision=evaluation,
        discovery_run=discovery,
        historical_runs=(historical,),
        run_id=uuid4(),
        job_id=uuid4(),
        site="site-a",
        device_role="access",
        platform="iosxe",
    )


def _device(
    device_id: str, device_type: str, manufacturer: str, model: str, platform: str
):
    from backend.app.inventory.entities import (
        Device,
        DeviceType,
        Manufacturer,
        Platform,
    )

    return Device(
        name=device_id,
        device_type=DeviceType(
            manufacturer=Manufacturer(name=manufacturer, slug=manufacturer.lower()),
            model=device_type,
            slug=f"{device_type.lower()}-{model.lower()}",
            part_number=None,
            u_height=None,
            is_full_depth=None,
        ),
        platform=Platform(name=platform, slug=platform.lower()),
        serial=None,
    )
