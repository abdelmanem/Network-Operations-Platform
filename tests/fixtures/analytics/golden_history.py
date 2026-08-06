from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from backend.app.analytics.context import (
    HistoricalAnalyticsContext,
    HistoricalFindingEntry,
    HistoricalRunEntry,
)


def build_context() -> HistoricalAnalyticsContext:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    runs = (
        HistoricalRunEntry(
            run_id=UUID("11111111-1111-1111-1111-111111111111"),
            started_at=base,
            completed_at=base + timedelta(minutes=20),
            total_devices=10,
            successful_targets=10,
            total_targets=10,
            compliance_score=88,
            critical_findings=1,
            major_findings=2,
            minor_findings=3,
            missing_devices=0,
            extra_devices=0,
            changed_devices=1,
            discovered_devices=10,
            inventory_accuracy=98.0,
            netbox_sync=99.0,
            risk_score=0.35,
        ),
        HistoricalRunEntry(
            run_id=UUID("22222222-2222-2222-2222-222222222222"),
            started_at=base + timedelta(days=7),
            completed_at=base + timedelta(days=7, minutes=25),
            total_devices=12,
            successful_targets=11,
            total_targets=12,
            compliance_score=81,
            critical_findings=2,
            major_findings=4,
            minor_findings=2,
            missing_devices=1,
            extra_devices=1,
            changed_devices=2,
            discovered_devices=12,
            inventory_accuracy=95.0,
            netbox_sync=97.0,
            risk_score=0.6,
        ),
        HistoricalRunEntry(
            run_id=UUID("33333333-3333-3333-3333-333333333333"),
            started_at=base + timedelta(days=14),
            completed_at=base + timedelta(days=14, minutes=18),
            total_devices=14,
            successful_targets=13,
            total_targets=14,
            compliance_score=92,
            critical_findings=0,
            major_findings=1,
            minor_findings=2,
            missing_devices=0,
            extra_devices=0,
            changed_devices=1,
            discovered_devices=14,
            inventory_accuracy=99.0,
            netbox_sync=100.0,
            risk_score=0.2,
        ),
    )
    findings = (
        HistoricalFindingEntry(
            finding_id=uuid4(),
            run_id=runs[0].run_id,
            title="Configuration drift",
            severity="critical",
            resolved=False,
            created_at=runs[0].started_at,
            resolved_at=None,
            device_id="r1",
            platform="iosxe",
            vendor="Cisco",
        ),
        HistoricalFindingEntry(
            finding_id=uuid4(),
            run_id=runs[1].run_id,
            title="Configuration drift",
            severity="critical",
            resolved=False,
            created_at=runs[1].started_at,
            resolved_at=None,
            device_id="r1",
            platform="iosxe",
            vendor="Cisco",
        ),
        HistoricalFindingEntry(
            finding_id=uuid4(),
            run_id=runs[2].run_id,
            title="Configuration drift",
            severity="critical",
            resolved=True,
            created_at=runs[2].started_at,
            resolved_at=runs[2].completed_at,
            device_id="r1",
            platform="iosxe",
            vendor="Cisco",
        ),
    )
    return HistoricalAnalyticsContext(runs=runs, findings=findings)
