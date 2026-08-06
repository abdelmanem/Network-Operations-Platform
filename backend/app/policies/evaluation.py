"""Policy evaluation package helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID

from backend.app.compliance.policies.models import Policy
from backend.app.compliance.rules.base import Rule
from backend.app.evaluation.exceptions import PolicyEvaluationError
from backend.app.evaluation.registry import EvaluationRuleRegistry
from backend.app.policies.models import PolicyPackage

ASSIGNMENT_TO_TAG: dict[str, str] = {
    "organization": "organization",
    "site": "site",
    "building": "building",
    "floor": "floor",
    "rack": "rack",
    "vendor": "vendor",
    "platform": "platform",
    "device_type": "device_type",
    "device": "device",
}


@dataclass(slots=True)
class PolicyPackageResolver:
    """Resolve compiled policy packages into executable compliance policies."""

    rule_registry: EvaluationRuleRegistry = field(
        default_factory=EvaluationRuleRegistry
    )

    def resolve(self, packages: Iterable[PolicyPackage]) -> tuple[Policy, ...]:
        """Convert packages to executable policies."""
        return tuple(policy for policy, _ in self.resolve_with_versions(packages))

    def resolve_with_versions(
        self,
        packages: Iterable[PolicyPackage],
    ) -> tuple[tuple[Policy, str], ...]:
        """Convert packages to executable policies and preserve selected versions."""
        if not packages:
            return ()

        packages_by_key: dict[str, list[PolicyPackage]] = {}
        package_by_id: dict[UUID, PolicyPackage] = {}
        for package in packages:
            packages_by_key.setdefault(package.policy_key, []).append(package)
            package_by_id[package.policy_id] = package

        compiled_policies: list[tuple[Policy, str]] = []
        for _, entries in packages_by_key.items():
            entries.sort(key=lambda item: item.version, reverse=True)
            selected_package = entries[0]
            compiled_policies.append(
                (
                    self._build_policy(selected_package, package_by_id),
                    selected_package.version.as_string(),
                )
            )

        return tuple(compiled_policies)

    def _build_policy(
        self,
        package: PolicyPackage,
        package_by_id: dict[UUID, PolicyPackage],
    ) -> Policy:
        ordered_packages = self._resolve_inherited_packages(package, package_by_id)
        rule_keys: list[str] = []
        seen: set[str] = set()
        for resolved in ordered_packages:
            for rule_ref in resolved.rules:
                if rule_ref.key not in seen:
                    seen.add(rule_ref.key)
                    rule_keys.append(rule_ref.key)

        rules: list[Rule] = []
        for key in rule_keys:
            try:
                rules.append(self.rule_registry.get(key))
            except KeyError as exc:
                raise PolicyEvaluationError(
                    f"Compiled policy {package.policy_key}@"
                    f"{package.version.as_string()} "
                    f"references unknown rule {key!r}."
                ) from exc

        tags = tuple(
            tag
            for tag in (
                self._assignment_to_tag(assignment.scope, assignment.value)
                for assignment in package.assignments
                if assignment.scope in ASSIGNMENT_TO_TAG and assignment.value.strip()
            )
            if tag is not None
        )

        return Policy(
            id=package.policy_id,
            name=package.policy_key,
            description=(
                f"Compiled policy package {package.policy_key}@"
                f"{package.version.as_string()}"
            ),
            rules=tuple(rules),
            baselines=tuple(),
            enabled=True,
            tags=tags,
            created_at=package.compiled_at,
        )

    def _resolve_inherited_packages(
        self,
        package: PolicyPackage,
        package_by_id: dict[UUID, PolicyPackage],
        visited: set[UUID] | None = None,
    ) -> tuple[PolicyPackage, ...]:
        if visited is None:
            visited = set()

        ordered: list[PolicyPackage] = []
        for parent_id in package.inherited_ids:
            if parent_id in visited:
                continue
            visited.add(parent_id)
            parent = package_by_id.get(parent_id)
            if parent is None:
                continue
            ordered.extend(
                self._resolve_inherited_packages(parent, package_by_id, visited)
            )
            ordered.append(parent)
        ordered.append(package)
        return tuple(ordered)

    @staticmethod
    def _assignment_to_tag(scope: str, value: str) -> str | None:
        key = ASSIGNMENT_TO_TAG.get(scope)
        if key is None or not value.strip():
            return None
        return f"{key}:{value.strip()}"
