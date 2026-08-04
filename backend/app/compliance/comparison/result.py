"""Comparison result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.compliance.comparison.models import ComparisonMetrics, ComparisonTarget
from backend.app.compliance.domain.entities import ComplianceEntity
from backend.app.compliance.domain.enums import ComparisonStatus
from backend.app.compliance.findings.models import Finding


@dataclass(frozen=True, slots=True)
class ComparisonResult(ComplianceEntity[UUID]):
    """Immutable comparison result model."""

    target: ComparisonTarget
    status: ComparisonStatus
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    metrics: ComparisonMetrics | None = None
    summary: str | None = None
    compared_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        target: ComparisonTarget,
        status: ComparisonStatus,
        *,
        findings: tuple[Finding, ...] | None = None,
        metrics: ComparisonMetrics | None = None,
        summary: str | None = None,
        compared_at: datetime | None = None,
    ) -> ComparisonResult:
        """Create a comparison result with a generated identity."""

        return cls(
            id=uuid4(),
            target=target,
            status=status,
            findings=() if findings is None else findings,
            metrics=metrics,
            summary=summary,
            compared_at=datetime.now(UTC) if compared_at is None else compared_at,
        )
