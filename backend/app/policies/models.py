"""Immutable policy domain models."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID, uuid4

from backend.app.policies.exceptions import (
    InvalidVersionError,
    PolicyValidationError,
)
from backend.app.policies.lifecycle import PolicyLifecycle
from backend.app.policies.versioning import VersionChange


@dataclass(frozen=True, slots=True)
class PolicyVersion:
    """Immutable semantic version for a policy."""

    major: int
    minor: int
    patch: int
    history: tuple[PolicyVersion, ...] = field(default_factory=tuple)

    @classmethod
    def create(
        cls,
        value: str,
        history: tuple[PolicyVersion, ...] | None = None,
    ) -> PolicyVersion:
        parts = value.split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise InvalidVersionError(f"Invalid version: {value}")

        version = cls(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))
        if history is None:
            return version
        return cls(version.major, version.minor, version.patch, history=history)

    def as_string(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __iter__(self) -> Iterator[int]:
        yield self.major
        yield self.minor
        yield self.patch

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PolicyVersion):
            return NotImplemented
        return tuple(self) < tuple(other)

    def __le__(self, other: object) -> bool:
        if not isinstance(other, PolicyVersion):
            return NotImplemented
        return tuple(self) <= tuple(other)

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, PolicyVersion):
            return NotImplemented
        return tuple(self) > tuple(other)

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, PolicyVersion):
            return NotImplemented
        return tuple(self) >= tuple(other)


@dataclass(frozen=True, slots=True)
class RuleReference:
    """Reference to a reusable rule definition."""

    key: str
    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class BaselineReference:
    """Reference to a baseline that a policy depends on."""

    key: str
    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyAssignment:
    """Deterministic assignment target for policy scope."""

    scope: str
    value: str


class PolicyScope:
    """Supported assignment scopes."""

    ORGANIZATION: ClassVar[str] = "organization"
    SITE: ClassVar[str] = "site"
    BUILDING: ClassVar[str] = "building"
    FLOOR: ClassVar[str] = "floor"
    RACK: ClassVar[str] = "rack"
    VENDOR: ClassVar[str] = "vendor"
    PLATFORM: ClassVar[str] = "platform"
    DEVICE_TYPE: ClassVar[str] = "device_type"
    DEVICE: ClassVar[str] = "device"


class PolicyInheritanceScope:
    """Supported inheritance levels for policies."""

    GLOBAL: ClassVar[str] = "global"
    ORGANIZATION: ClassVar[str] = "organization"
    SITE: ClassVar[str] = "site"
    DEVICE_GROUP: ClassVar[str] = "device_group"
    DEVICE: ClassVar[str] = "device"


@dataclass(frozen=True, slots=True)
class PolicyMetadata:
    """Supplemental metadata for a policy."""

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    owner: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Policy:
    """Immutable policy definition."""

    id: UUID
    key: str
    name: str
    version: PolicyVersion
    lifecycle: PolicyLifecycle
    metadata: PolicyMetadata
    rules: tuple[RuleReference, ...] = field(default_factory=tuple)
    baselines: tuple[BaselineReference, ...] = field(default_factory=tuple)
    assignments: tuple[PolicyAssignment, ...] = field(default_factory=tuple)
    inheritance: tuple[UUID, ...] = field(default_factory=tuple)
    inheritance_scope: str = PolicyInheritanceScope.GLOBAL
    previous_version: PolicyVersion | None = None
    version_history: tuple[PolicyVersion, ...] = field(default_factory=tuple)

    @classmethod
    def create(
        cls,
        *,
        key: str,
        name: str,
        version: PolicyVersion,
        lifecycle: PolicyLifecycle = PolicyLifecycle.DRAFT,
        metadata: PolicyMetadata | None = None,
        rules: tuple[RuleReference, ...] | None = None,
        baselines: tuple[BaselineReference, ...] | None = None,
        assignments: tuple[PolicyAssignment, ...] | None = None,
        inheritance: tuple[UUID, ...] | None = None,
        inheritance_scope: str | None = None,
        previous_version: PolicyVersion | None = None,
        version_history: tuple[PolicyVersion, ...] | None = None,
    ) -> Policy:
        return cls(
            id=uuid4(),
            key=key,
            name=name,
            version=version,
            lifecycle=lifecycle,
            metadata=metadata or PolicyMetadata(),
            rules=() if rules is None else rules,
            baselines=() if baselines is None else baselines,
            assignments=() if assignments is None else assignments,
            inheritance=() if inheritance is None else inheritance,
            inheritance_scope=(
                PolicyInheritanceScope.GLOBAL
                if inheritance_scope is None
                else inheritance_scope
            ),
            previous_version=previous_version,
            version_history=() if version_history is None else version_history,
        )

    def transition_to(self, lifecycle: PolicyLifecycle) -> Policy:
        if self.lifecycle is PolicyLifecycle.PUBLISHED:
            raise PolicyValidationError("Published policies are immutable")
        return Policy(
            id=self.id,
            key=self.key,
            name=self.name,
            version=self.version,
            lifecycle=lifecycle,
            metadata=self.metadata,
            rules=self.rules,
            baselines=self.baselines,
            assignments=self.assignments,
            inheritance=self.inheritance,
            inheritance_scope=self.inheritance_scope,
            previous_version=self.previous_version,
            version_history=self.version_history,
        )

    def bump_version(self, change: VersionChange) -> Policy:
        history = self.version_history + (self.version,)
        if change is VersionChange.MAJOR:
            next_version = PolicyVersion(
                self.version.major,
                0,
                0,
                history=history,
            )
        elif change is VersionChange.MINOR:
            next_version = PolicyVersion(
                self.version.major,
                self.version.minor + 1,
                0,
                history=history,
            )
        else:
            next_version = PolicyVersion(
                self.version.major,
                self.version.minor,
                self.version.patch + 1,
                history=history,
            )
        return Policy(
            id=self.id,
            key=self.key,
            name=self.name,
            version=next_version,
            lifecycle=self.lifecycle,
            metadata=self.metadata,
            rules=self.rules,
            baselines=self.baselines,
            assignments=self.assignments,
            inheritance=self.inheritance,
            inheritance_scope=self.inheritance_scope,
            previous_version=self.version,
            version_history=history + (next_version,),
        )

    def with_inheritance(self, inheritance: tuple[UUID, ...]) -> Policy:
        return Policy(
            id=self.id,
            key=self.key,
            name=self.name,
            version=self.version,
            lifecycle=self.lifecycle,
            metadata=self.metadata,
            rules=self.rules,
            baselines=self.baselines,
            assignments=self.assignments,
            inheritance=inheritance,
            inheritance_scope=self.inheritance_scope,
            previous_version=self.previous_version,
            version_history=self.version_history,
        )

    def with_baselines(self, baselines: tuple[BaselineReference, ...]) -> Policy:
        return Policy(
            id=self.id,
            key=self.key,
            name=self.name,
            version=self.version,
            lifecycle=self.lifecycle,
            metadata=self.metadata,
            rules=self.rules,
            baselines=baselines,
            assignments=self.assignments,
            inheritance=self.inheritance,
            inheritance_scope=self.inheritance_scope,
            previous_version=self.previous_version,
            version_history=self.version_history,
        )

    def with_assignments(self, assignments: tuple[PolicyAssignment, ...]) -> Policy:
        return Policy(
            id=self.id,
            key=self.key,
            name=self.name,
            version=self.version,
            lifecycle=self.lifecycle,
            metadata=self.metadata,
            rules=self.rules,
            baselines=self.baselines,
            assignments=assignments,
            inheritance=self.inheritance,
            inheritance_scope=self.inheritance_scope,
            previous_version=self.previous_version,
            version_history=self.version_history,
        )


@dataclass(frozen=True, slots=True)
class RuleSet:
    """Immutable aggregate of rules in a policy package."""

    rules: tuple[RuleReference, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PolicyPackage:
    """Compiled immutable evaluation package for a policy."""

    policy_id: UUID
    policy_key: str
    version: PolicyVersion
    rules: tuple[RuleReference, ...]
    baselines: tuple[BaselineReference, ...]
    assignments: tuple[PolicyAssignment, ...]
    inherited_ids: tuple[UUID, ...]
    compiled_at: datetime


@dataclass(frozen=True, slots=True)
class PolicyMetadataRecord:
    """Compatibility wrapper for policy metadata."""

    policy_id: UUID
    metadata: PolicyMetadata
