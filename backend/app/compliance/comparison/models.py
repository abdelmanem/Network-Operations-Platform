"""Comparison input models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from backend.app.compliance.policies.models import Baseline, Policy


@dataclass(frozen=True, slots=True)
class ComparisonTarget:
    """Target of a compliance comparison."""

    policy: Policy
    baseline: Baseline
    subject_type: str
    subject_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def policy_id(self) -> UUID:
        """Return the policy identity."""

        return self.policy.id

    @property
    def baseline_id(self) -> UUID:
        """Return the baseline identity."""

        return self.baseline.id


@dataclass(frozen=True, slots=True)
class ComparisonMetrics:
    """Summary metrics for a comparison."""

    total_findings: int
    compliant_checks: int
    failed_checks: int
    warning_checks: int = 0
