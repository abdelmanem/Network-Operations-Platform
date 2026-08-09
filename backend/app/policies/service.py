"""Service facade for policy compilation and validation."""

from __future__ import annotations

from uuid import UUID

from backend.app.audit.application.services import AuditService
from backend.app.policies.engine import PolicyEngine
from backend.app.policies.models import Policy, PolicyPackage


class PolicyService:
    """High-level service for working with policies."""

    def __init__(
        self,
        engine: PolicyEngine | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.engine = engine or PolicyEngine()
        self.audit_service = audit_service

    def compile(self, policy: Policy) -> PolicyPackage:
        return self.engine.compile(policy)

    def validate(self, policy: Policy) -> Policy:
        return self.engine.validate(policy)

    def record_policy_change(
        self,
        *,
        policy: Policy,
        action: str,
        actor_id: object | None = None,
        tenant_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        if self.audit_service is None:
            return
        self.audit_service.record_policy_change(
            policy_id=policy.id,
            policy_key=policy.key,
            action=action,
            actor_id=UUID(actor_id) if isinstance(actor_id, str) else None,
            tenant_id=tenant_id,
            request_id=request_id,
            metadata={"name": policy.name, "version": policy.version.as_string()},
        )
