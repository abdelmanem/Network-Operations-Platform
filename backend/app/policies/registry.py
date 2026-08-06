"""Simple registry for tracking policy definitions."""

from __future__ import annotations

from backend.app.policies.models import Policy


class PolicyRegistry:
    """In-memory registry for policy instances."""

    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}

    def register(self, policy: Policy) -> Policy:
        self._policies[policy.key] = policy
        return policy

    def get(self, key: str) -> Policy | None:
        return self._policies.get(key)

    def list(self) -> tuple[Policy, ...]:
        return tuple(self._policies.values())
