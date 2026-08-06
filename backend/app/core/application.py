"""Application factory and runtime container."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from backend.app.api.router import api_router
from backend.app.auth.api.router import router as auth_router
from backend.app.collectors.execution.result import CollectorExecutionResult
from backend.app.collectors.execution.status import CollectorExecutionStatus
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.collectors.runtime.job import CollectorJob
from backend.app.comparison.engine import ComparisonEngine
from backend.app.config.logging import configure_logging
from backend.app.config.settings import Settings, get_settings
from backend.app.core.constants import APP_NAME, APP_PACKAGE, APP_VERSION
from backend.app.core.lifecycle import ApplicationLifecycleManager, lifecycle_context
from backend.app.core.metadata import ApplicationMetadata
from backend.app.core.plugins import PluginRegistry
from backend.app.database.session import SessionLocal
from backend.app.evaluation.engine import EvaluationEngine
from backend.app.events.dispatcher import EventDispatcher
from backend.app.events.registry import EventHandlerRegistry
from backend.app.inventory.dto import InventorySnapshot
from backend.app.jobs.manager import JobManager
from backend.app.jobs.repository import InMemoryJobRepository
from backend.app.orchestration.coordinator import DiscoveryCoordinator
from backend.app.scheduler.registry import WorkerRegistry
from backend.app.orchestration.engine import OrchestrationEngine
from backend.app.orchestration.workflow import WorkflowEngine
from backend.app.persistence.unit_of_work import PersistenceUnitOfWork


class _PlaceholderInventoryService:
    """Lightweight inventory service used for orchestration wiring."""

    async def synchronize(self, *, force_refresh: bool = False) -> InventorySnapshot:
        return InventorySnapshot(devices=())


class _PlaceholderCollectorRuntime:
    """Minimal collector runtime adapter for orchestration wiring."""

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def submit(
        self,
        context: CollectorRuntimeContext,
        *,
        priority: int = 0,
    ) -> CollectorJob:
        return CollectorJob(context=context, priority=priority)

    async def run_job(self, job: CollectorJob) -> CollectorExecutionResult:
        return CollectorExecutionResult(
            job_id=job.id,
            collector_name="placeholder",
            target=job.context.target,
            status=CollectorExecutionStatus.SUCCEEDED,
        )


@dataclass(slots=True)
class ApplicationContainer:
    """Compose framework services for dependency injection."""

    settings: Settings
    metadata: ApplicationMetadata
    plugins: PluginRegistry
    lifecycle: ApplicationLifecycleManager
    event_registry: EventHandlerRegistry
    event_dispatcher: EventDispatcher
    engine: OrchestrationEngine
    repository: InMemoryJobRepository
    job_manager: JobManager
    worker_registry: WorkerRegistry


def create_application(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    metadata = ApplicationMetadata(
        name=APP_NAME,
        version=app_settings.app_version or APP_VERSION,
        package=APP_PACKAGE,
        description="Core framework for Network Operations Platform.",
    )
    lifecycle_manager = ApplicationLifecycleManager()
    event_registry = EventHandlerRegistry()
    event_dispatcher = EventDispatcher(event_registry)
    workflow = WorkflowEngine(
        inventory_service=_PlaceholderInventoryService(),
        discovery_coordinator=DiscoveryCoordinator(_PlaceholderCollectorRuntime()),
        comparison_engine=ComparisonEngine(),
        evaluation_engine=EvaluationEngine(),
        unit_of_work_factory=lambda: PersistenceUnitOfWork(SessionLocal()),
    )
    engine = OrchestrationEngine(workflow)
    repository = InMemoryJobRepository()
    job_manager = JobManager(
        engine=engine,
        repository=repository,
        event_publisher=None,
        worker_count=1,
    )
    container = ApplicationContainer(
        settings=app_settings,
        metadata=metadata,
        plugins=PluginRegistry(),
        lifecycle=lifecycle_manager,
        event_registry=event_registry,
        event_dispatcher=event_dispatcher,
        engine=engine,
        repository=repository,
        job_manager=job_manager,
        worker_registry=WorkerRegistry(),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with lifecycle_context(container.lifecycle):
            yield

    app = FastAPI(
        title=metadata.name,
        version=metadata.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_logging_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/auth"):
            response.headers["X-Auth-Handled"] = "true"

        job_id = None
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                body = response.body
                if isinstance(body, memoryview):
                    body = bytes(body)
                payload = json.loads(body.decode("utf-8"))
                if isinstance(payload, dict) and "job_id" in payload:
                    job_id = payload.get("job_id")
            except Exception:
                job_id = None

        logging.getLogger("backend.app.api").info(
            "request_complete",
            extra={
                "request_id": request_id,
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "job_id": job_id,
            },
        )
        return response

    @app.middleware("http")
    async def security_headers_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "error": "validation_error"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        status_map = {
            status.HTTP_400_BAD_REQUEST: "bad_request",
            status.HTTP_401_UNAUTHORIZED: "unauthorized",
            status.HTTP_403_FORBIDDEN: "forbidden",
            status.HTTP_404_NOT_FOUND: "not_found",
            status.HTTP_409_CONFLICT: "conflict",
            status.HTTP_422_UNPROCESSABLE_ENTITY: "validation_error",
        }
        error_code = status_map.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error": error_code},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "error": "internal_server_error",
            },
        )

    app.state.container = container
    app.include_router(api_router)
    app.include_router(auth_router)
    return app
