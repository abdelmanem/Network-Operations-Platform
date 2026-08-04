"""Policy and baseline models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID, uuid4

from backend.app.compliance.domain.entities import ComplianceEntity
from backend.app.compliance.rules.base import Rule


@dataclass(frozen=True, slots=True)
class Baseline(ComplianceEntity[UUID]):
    """Immutable compliance baseline."""

    name: str
    description: str | None = None
    scope: str | None = None
    version: str = "1.0"
    expected_state: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        *,
        description: str | None = None,
        scope: str | None = None,
        version: str = "1.0",
        expected_state: Mapping[str, object] | None = None,
        created_at: datetime | None = None,
    ) -> Baseline:
        """Create a baseline with a generated identity."""

        return cls(
            id=uuid4(),
            name=name,
            description=description,
            scope=scope,
            version=version,
            expected_state=(
                MappingProxyType({})
                if expected_state is None
                else MappingProxyType(dict(expected_state))
            ),
            created_at=datetime.now(UTC) if created_at is None else created_at,
        )


@dataclass(frozen=True, slots=True)
class Policy(ComplianceEntity[UUID]):
    """Immutable compliance policy."""

    name: str
    description: str | None = None
    rules: tuple[Rule, ...] = field(default_factory=tuple)
    baselines: tuple[Baseline, ...] = field(default_factory=tuple)
    enabled: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        *,
        description: str | None = None,
        rules: tuple[Rule, ...] | None = None,
        baselines: tuple[Baseline, ...] | None = None,
        enabled: bool = True,
        tags: tuple[str, ...] | None = None,
        created_at: datetime | None = None,
    ) -> Policy:
        """Create a policy with a generated identity."""

        return cls(
            id=uuid4(),
            name=name,
            description=description,
            rules=() if rules is None else rules,
            baselines=() if baselines is None else baselines,
            enabled=enabled,
            tags=() if tags is None else tags,
            created_at=datetime.now(UTC) if created_at is None else created_at,
        )
