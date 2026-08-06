"""Service facade for policy compilation and validation."""

from __future__ import annotations

from backend.app.policies.engine import PolicyEngine
from backend.app.policies.models import Policy, PolicyPackage


class PolicyService:
    """High-level service for working with policies."""

    def __init__(self, engine: PolicyEngine | None = None) -> None:
        self.engine = engine or PolicyEngine()

    def compile(self, policy: Policy) -> PolicyPackage:
        return self.engine.compile(policy)

    def validate(self, policy: Policy) -> Policy:
        return self.engine.validate(policy)
