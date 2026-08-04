"""Finding and recommendation models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID, uuid4

from backend.app.compliance.domain.entities import ComplianceEntity
from backend.app.compliance.findings.evidence import Evidence
from backend.app.compliance.findings.severity import Severity


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Immutable remediation recommendation."""

    summary: str
    rationale: str | None = None
    steps: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Finding(ComplianceEntity[UUID]):
    """Immutable compliance finding."""

    rule_id: UUID
    title: str
    severity: Severity
    description: str | None = None
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    recommendation: Recommendation | None = None
    observed_state: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
    expected_state: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        rule_id: UUID,
        title: str,
        severity: Severity,
        *,
        description: str | None = None,
        evidence: tuple[Evidence, ...] | None = None,
        recommendation: Recommendation | None = None,
        observed_state: Mapping[str, object] | None = None,
        expected_state: Mapping[str, object] | None = None,
        created_at: datetime | None = None,
    ) -> Finding:
        """Create a finding with a generated identity."""

        return cls(
            id=uuid4(),
            rule_id=rule_id,
            title=title,
            severity=severity,
            description=description,
            evidence=() if evidence is None else evidence,
            recommendation=recommendation,
            observed_state=(
                MappingProxyType({})
                if observed_state is None
                else MappingProxyType(dict(observed_state))
            ),
            expected_state=(
                MappingProxyType({})
                if expected_state is None
                else MappingProxyType(dict(expected_state))
            ),
            created_at=datetime.now(UTC) if created_at is None else created_at,
        )
