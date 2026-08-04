"""Rule domain model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from backend.app.compliance.domain.entities import ComplianceEntity

if TYPE_CHECKING:
    from backend.app.compliance.policies.models import Baseline

from backend.app.compliance.rules.metadata import RuleMetadata


@dataclass(frozen=True, slots=True)
class Rule(ComplianceEntity[UUID]):
    """Immutable compliance rule model."""

    key: str
    name: str
    metadata: RuleMetadata
    description: str | None = None
    baseline: Baseline | None = None
    expected_state: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @classmethod
    def create(
        cls,
        key: str,
        name: str,
        metadata: RuleMetadata,
        *,
        description: str | None = None,
        baseline: Baseline | None = None,
        expected_state: Mapping[str, object] | None = None,
    ) -> Rule:
        """Create a rule with a generated identity."""

        return cls(
            id=uuid4(),
            key=key,
            name=name,
            metadata=metadata,
            description=description,
            baseline=baseline,
            expected_state=(
                MappingProxyType({})
                if expected_state is None
                else MappingProxyType(dict(expected_state))
            ),
        )
