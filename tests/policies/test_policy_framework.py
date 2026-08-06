from __future__ import annotations

import pytest
from backend.app.policies.engine import PolicyEngine
from backend.app.policies.exceptions import (
    CircularInheritanceError,
    InvalidAssignmentError,
    MissingBaselineError,
    PolicyValidationError,
)
from backend.app.policies.lifecycle import PolicyLifecycle
from backend.app.policies.models import (
    BaselineReference,
    Policy,
    PolicyAssignment,
    PolicyPackage,
    PolicyScope,
    PolicyVersion,
    RuleReference,
)
from backend.app.policies.repository import InMemoryPolicyRepository
from backend.app.policies.service import PolicyService
from backend.app.policies.versioning import VersionChange


def test_policy_lifecycle_transitions_and_immutability() -> None:
    policy = Policy.create(
        key="policy-1",
        name="Base Policy",
        version=PolicyVersion.create("1.0.0"),
        lifecycle=PolicyLifecycle.DRAFT,
    )

    assert policy.lifecycle is PolicyLifecycle.DRAFT

    published = policy.transition_to(PolicyLifecycle.PUBLISHED)
    assert published.lifecycle is PolicyLifecycle.PUBLISHED

    try:
        published.transition_to(PolicyLifecycle.ARCHIVED)
    except PolicyValidationError:
        pass
    else:
        raise AssertionError("Published policies should be immutable")


def test_versioning_tracks_history_and_previous_version() -> None:
    initial = Policy.create(
        key="policy-2",
        name="Versioned Policy",
        version=PolicyVersion.create("1.0.0"),
    )
    major = initial.bump_version(VersionChange.MAJOR)
    minor = major.bump_version(VersionChange.MINOR)
    patch = minor.bump_version(VersionChange.PATCH)

    assert patch.version.as_string() == "1.1.1"
    assert patch.previous_version is not None
    assert patch.previous_version.as_string() == "1.1.0"
    assert patch.version_history[-1].as_string() == "1.1.1"


def test_compiler_builds_immutable_package() -> None:
    policy = Policy.create(
        key="policy-3",
        name="Compiled Policy",
        version=PolicyVersion.create("2.0.0"),
        rules=(RuleReference(key="rule-1", name="Rule One"),),
        baselines=(BaselineReference(key="baseline-1", name="Baseline One"),),
        assignments=(
            PolicyAssignment(
                scope=PolicyScope.ORGANIZATION,
                value="org-1",
            ),
        ),
    )

    package = PolicyEngine().compile(policy)

    assert isinstance(package, PolicyPackage)
    assert package.policy_id == policy.id
    assert package.rules[0].key == "rule-1"
    assert package.compiled_at is not None


def test_validation_detects_inheritance_and_assignment_errors() -> None:
    parent = Policy.create(
        key="parent",
        name="Parent",
        version=PolicyVersion.create("1.0.0"),
    )
    child = Policy.create(
        key="child",
        name="Child",
        version=PolicyVersion.create("1.0.0"),
        inheritance=(parent.id,),
    )

    with pytest.raises(CircularInheritanceError):
        PolicyEngine().validate(child.with_inheritance((child.id,)))

    with pytest.raises(MissingBaselineError):
        PolicyEngine().validate(
            child.with_inheritance((parent.id,)).with_baselines(
                (BaselineReference(key="missing", name="Missing"),)
            )
        )

    with pytest.raises(InvalidAssignmentError):
        PolicyEngine().validate(
            child.with_assignments(
                (
                    PolicyAssignment(
                        scope=PolicyScope.ORGANIZATION,
                        value="",
                    ),
                )
            )
        )


def test_repository_is_read_only_for_published_versions() -> None:
    repo = InMemoryPolicyRepository()
    published = Policy.create(
        key="published",
        name="Published",
        version=PolicyVersion.create("1.0.0"),
        lifecycle=PolicyLifecycle.PUBLISHED,
    )
    repo.add(published)

    with pytest.raises(PolicyValidationError):
        repo.update(published, published.transition_to(PolicyLifecycle.ARCHIVED))

    assert repo.get(published.id) == published


def test_service_exposes_compilation_and_validation() -> None:
    policy = Policy.create(
        key="policy-4",
        name="Service Policy",
        version=PolicyVersion.create("1.0.0"),
        rules=(RuleReference(key="rule-2", name="Rule Two"),),
        baselines=(BaselineReference(key="baseline-2", name="Baseline Two"),),
        assignments=(PolicyAssignment(scope=PolicyScope.SITE, value="site-a"),),
    )
    service = PolicyService(engine=PolicyEngine())

    package = service.compile(policy)
    validated = service.validate(policy)

    assert isinstance(package, PolicyPackage)
    assert validated.id == policy.id
    assert validated.lifecycle is PolicyLifecycle.DRAFT
