"""Audit logging boundary for immutable platform activity records."""

from backend.app.audit.application.services import AuditService
from backend.app.audit.domain.models import AuditRecord

__all__ = ["AuditRecord", "AuditService"]
