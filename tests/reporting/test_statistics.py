from __future__ import annotations

from backend.app.reporting.statistics import StatisticsCalculator
from tests.fixtures.reporting.golden_context import build_report_context


def test_statistics_calculator_reports_expected_values() -> None:
    context = build_report_context()
    calculator = StatisticsCalculator()

    statistics = calculator.calculate(context)

    assert statistics.total_devices == 3
    assert statistics.reachable_devices == 3
    assert statistics.unreachable_devices == 0
    assert statistics.discovery_success_pct == 80.0
    assert statistics.netbox_accuracy_pct == 33.33
    assert statistics.compliance_score == 65
    assert statistics.critical_findings == 1
    assert statistics.major_findings == 0
    assert statistics.minor_findings == 0
    assert statistics.missing_devices == 1
    assert statistics.extra_devices == 0
    assert statistics.changed_devices == 1
    assert statistics.interface_changes == 1
    assert statistics.vlan_changes == 0
    assert statistics.configuration_changes == 0
