"""Deterministic inheritance resolution for policies."""

from __future__ import annotations

from uuid import UUID

from backend.app.policies.models import Policy


class InheritanceResolver:
    """Resolve inheritance in a deterministic order."""

    def resolve(self, policy: Policy) -> tuple[UUID, ...]:
        return tuple(sorted(policy.inheritance, key=lambda item: str(item)))
