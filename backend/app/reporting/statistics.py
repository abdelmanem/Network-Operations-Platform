"""Report statistics calculation from cached context."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from backend.app.comparison.diff import DifferenceType
from backend.app.compliance.findings.models import Finding
from backend.app.compliance.findings.severity import SeverityLevel
from backend.app.reporting.context import ReportContext


@dataclass(frozen=True, slots=True)
class ReportStatistics:
    """Immutable report statistics snapshot."""

    total_devices: int = 0
    reachable_devices: int = 0
    unreachable_devices: int = 0
    discovery_success_pct: float = 0.0
    netbox_accuracy_pct: float = 100.0
    compliance_score: int = 100
    critical_findings: int = 0
    major_findings: int = 0
    minor_findings: int = 0
    device_type_counts: tuple[tuple[str, int], ...] = ()
    vendor_counts: tuple[tuple[str, int], ...] = ()
    platform_counts: tuple[tuple[str, int], ...] = ()
    missing_devices: int = 0
    extra_devices: int = 0
    changed_devices: int = 0
    interface_changes: int = 0
    vlan_changes: int = 0
    configuration_changes: int = 0


class StatisticsCalculator:
    """Calculate reusable statistics from cached report context."""

    def calculate(self, context: ReportContext) -> ReportStatistics:
        """Return statistics derived from cached immutable inputs."""

        total_devices = self._total_devices(context)
        reachable_devices = self._reachable_devices(context)
        unreachable_devices = max(total_devices - reachable_devices, 0)
        discovery_success_pct = self._discovery_success_pct(context)
        netbox_accuracy_pct = self._netbox_accuracy_pct(context)
        compliance_score = self._compliance_score(context)
        critical, major, minor = self._finding_counts(context)
        device_types = self._device_type_counts(context)
        vendors = self._vendor_counts(context)
        platforms = self._platform_counts(context)
        missing, extra, changed = self._device_drift_counts(context)
        interface_changes, vlan_changes, config_changes = self._change_counts(context)

        return ReportStatistics(
            total_devices=total_devices,
            reachable_devices=reachable_devices,
            unreachable_devices=unreachable_devices,
            discovery_success_pct=discovery_success_pct,
            netbox_accuracy_pct=netbox_accuracy_pct,
            compliance_score=compliance_score,
            critical_findings=critical,
            major_findings=major,
            minor_findings=minor,
            device_type_counts=device_types,
            vendor_counts=vendors,
            platform_counts=platforms,
            missing_devices=missing,
            extra_devices=extra,
            changed_devices=changed,
            interface_changes=interface_changes,
            vlan_changes=vlan_changes,
            configuration_changes=config_changes,
        )

    def _total_devices(self, context: ReportContext) -> int:
        if context.netbox_inventory is not None:
            return len(context.netbox_inventory.devices)
        if context.live_snapshot is not None:
            return len(context.live_snapshot.devices)
        return 0

    def _reachable_devices(self, context: ReportContext) -> int:
        if context.live_snapshot is not None:
            return len(context.live_snapshot.devices)
        if context.discovery_run is not None:
            return context.discovery_run.successful_targets
        return 0

    def _discovery_success_pct(self, context: ReportContext) -> float:
        run = context.discovery_run
        if run is None or run.total_targets == 0:
            return 100.0 if context.live_snapshot is not None else 0.0
        return round((run.successful_targets / run.total_targets) * 100.0, 2)

    def _netbox_accuracy_pct(self, context: ReportContext) -> float:
        netbox_count = (
            len(context.netbox_inventory.devices)
            if context.netbox_inventory is not None
            else 0
        )
        if netbox_count == 0:
            return 100.0
        comparison = context.comparison_result
        if comparison is None or comparison.metrics is None:
            matched = self._reachable_devices(context)
            return round((matched / netbox_count) * 100.0, 2)
        metrics = comparison.metrics
        accurate = netbox_count - metrics.missing - metrics.modified
        accurate = max(accurate, 0)
        return round((accurate / netbox_count) * 100.0, 2)

    def _compliance_score(self, context: ReportContext) -> int:
        if context.evaluation_decision is not None:
            return context.evaluation_decision.compliance_score
        if (
            context.comparison_result is not None
            and context.comparison_result.is_compliant
        ):
            return 100
        return 0

    def _finding_counts(self, context: ReportContext) -> tuple[int, int, int]:
        findings = self._all_findings(context)
        critical = 0
        major = 0
        minor = 0
        for finding in findings:
            level = finding.severity.level
            if level == SeverityLevel.CRITICAL:
                critical += 1
            elif level == SeverityLevel.HIGH:
                major += 1
            else:
                minor += 1
        return critical, major, minor

    def _all_findings(self, context: ReportContext) -> tuple[Finding, ...]:
        if context.comparison_result is not None:
            return context.comparison_result.findings
        return ()

    def _device_type_counts(
        self,
        context: ReportContext,
    ) -> tuple[tuple[str, int], ...]:
        counter: Counter[str] = Counter()
        if context.netbox_inventory is not None:
            for netbox_device in context.netbox_inventory.devices:
                counter[netbox_device.device_type.model] += 1
        elif context.live_snapshot is not None:
            for snapshot_device in context.live_snapshot.devices:
                model = snapshot_device.model or "unknown"
                counter[model] += 1
        return tuple(sorted(counter.items()))

    def _vendor_counts(
        self,
        context: ReportContext,
    ) -> tuple[tuple[str, int], ...]:
        counter: Counter[str] = Counter()
        if context.netbox_inventory is not None:
            for netbox_device in context.netbox_inventory.devices:
                counter[netbox_device.device_type.manufacturer.name] += 1
        elif context.live_snapshot is not None:
            for snapshot_device in context.live_snapshot.devices:
                vendor = snapshot_device.manufacturer or "unknown"
                counter[vendor] += 1
        return tuple(sorted(counter.items()))

    def _platform_counts(
        self,
        context: ReportContext,
    ) -> tuple[tuple[str, int], ...]:
        counter: Counter[str] = Counter()
        if context.netbox_inventory is not None:
            for netbox_device in context.netbox_inventory.devices:
                platform = (
                    netbox_device.platform.name if netbox_device.platform else "unknown"
                )
                counter[platform] += 1
        elif context.live_snapshot is not None:
            for snapshot_device in context.live_snapshot.devices:
                platform = snapshot_device.platform or "unknown"
                counter[platform] += 1
        return tuple(sorted(counter.items()))

    def _device_drift_counts(self, context: ReportContext) -> tuple[int, int, int]:
        comparison = context.comparison_result
        if comparison is None or comparison.metrics is None:
            return 0, 0, 0
        metrics = comparison.metrics
        return metrics.missing, metrics.unexpected, metrics.modified

    def _change_counts(self, context: ReportContext) -> tuple[int, int, int]:
        comparison = context.comparison_result
        if comparison is None:
            return 0, 0, 0
        interface_changes = 0
        vlan_changes = 0
        configuration_changes = 0
        for difference in comparison.differences:
            if difference.difference_type != DifferenceType.MODIFIED:
                continue
            subject = difference.subject_type.lower()
            if subject == "interface":
                interface_changes += 1
            elif subject == "vlan":
                vlan_changes += 1
            elif subject in {"device", "configuration", "config"}:
                configuration_changes += 1
        return interface_changes, vlan_changes, configuration_changes
