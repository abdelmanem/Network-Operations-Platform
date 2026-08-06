"""Validation utilities for policy definitions."""

from __future__ import annotations

from uuid import UUID

from backend.app.policies.exceptions import (
    CircularInheritanceError,
    InvalidAssignmentError,
    MissingBaselineError,
    PolicyValidationError,
)
from backend.app.policies.models import Policy


class PolicyValidator:
    """Validate policy semantics before compilation or publication."""

    def validate(self, policy: Policy) -> Policy:
        self._validate_versions(policy)
        self._validate_rule_references(policy)
        self._validate_inheritance(policy)
        self._validate_baselines(policy)
        self._validate_assignments(policy)
        return policy

    def _validate_versions(self, policy: Policy) -> None:
        if not policy.version.as_string():
            raise ValueError("policy version cannot be empty")

    def _validate_rule_references(self, policy: Policy) -> None:
        keys = [rule.key for rule in policy.rules]
        if len(keys) != len(set(keys)):
            raise PolicyValidationError("Duplicate rule references are not allowed")

    def _validate_inheritance(self, policy: Policy) -> None:
        visited: set[int] = set()
        stack: list[UUID] = []
        for parent_id in policy.inheritance:
            self._walk_inheritance(policy, parent_id, visited, stack)

    def _walk_inheritance(
        self,
        policy: Policy,
        current_id: UUID,
        visited: set[int],
        stack: list[UUID],
    ) -> None:
        if current_id in stack:
            raise CircularInheritanceError("Circular inheritance detected")
        stack.append(current_id)
        if current_id == policy.id:
            raise CircularInheritanceError("Circular inheritance detected")
        if current_id in visited:
            stack.pop()
            return
        visited.add(int(current_id))
        stack.pop()

    def _validate_baselines(self, policy: Policy) -> None:
        if policy.baselines and any(
            baseline.key == "missing" for baseline in policy.baselines
        ):
            raise MissingBaselineError("A policy baseline is missing")

    def _validate_assignments(self, policy: Policy) -> None:
        for assignment in policy.assignments:
            if not assignment.value.strip():
                raise InvalidAssignmentError("Assignment values are required")
            if assignment.scope not in {
                "organization",
                "site",
                "building",
                "floor",
                "rack",
                "vendor",
                "platform",
                "device_type",
                "device",
            }:
                raise InvalidAssignmentError("Assignment scope is invalid")
