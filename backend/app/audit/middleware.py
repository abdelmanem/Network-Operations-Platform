from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.app.audit.application.services import AuditService


class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, audit_service: AuditService) -> None:
        super().__init__(app)
        self.audit_service = audit_service

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or request.headers.get(
            "x-request-id"
        )
        tenant_id = request.headers.get("X-Tenant-ID") or request.headers.get(
            "x-tenant-id"
        )
        response = await call_next(request)
        assert isinstance(response, Response)
        self.audit_service.record_api_activity(
            actor_id=None,
            tenant_id=tenant_id,
            resource_type="route",
            resource_id=request.url.path,
            outcome=str(response.status_code),
            request_id=request_id,
            metadata={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
            },
        )
        return response
