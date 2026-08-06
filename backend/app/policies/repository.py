"""Immutable repository implementations for policies."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.policies.exceptions import PolicyValidationError
from backend.app.policies.models import Policy


@dataclass(slots=True)
class InMemoryPolicyRepository:
    """Read-only repository for immutable policies."""

    policies: dict[str, Policy] = field(default_factory=dict)

    def add(self, policy: Policy) -> None:
        self.policies[policy.key] = policy

    def get(self, policy_id: object) -> Policy | None:
        for policy in self.policies.values():
            if policy.id == policy_id:
                return policy
        return None

    def list(self) -> tuple[Policy, ...]:
        return tuple(self.policies.values())

    def update(self, existing: Policy, updated: Policy) -> Policy:
        if existing.lifecycle is not None and existing.lifecycle.name == "PUBLISHED":
            raise PolicyValidationError("Published policies cannot be modified")
        self.policies[existing.key] = updated
        return updated
