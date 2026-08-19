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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from backend.app.api.router import api_router
from backend.app.auth.api.router import router as auth_router
from backend.app.cache.redis import build_cache_backend
from backend.app.collectors.cisco.factory import build_cisco_inventory_registry
from backend.app.collectors.cisco.inventory import CiscoInventoryParser
from backend.app.collectors.registry import CollectorRegistry
from backend.app.collectors.runtime.dispatcher import CollectorDispatcher
from backend.app.collectors.runtime.engine import CollectorRuntimeEngine
from backend.app.collectors.runtime.executor import CollectorExecutor
from backend.app.collectors.runtime.metrics import CollectorRuntimeMetrics
from backend.app.collectors.runtime.scheduler import CollectorScheduler
from backend.app.comparison.engine import ComparisonEngine
from backend.app.config.logging import configure_logging
from backend.app.config.settings import Settings, get_settings
from backend.app.core.constants import APP_NAME, APP_PACKAGE, APP_VERSION
from backend.app.core.lifecycle import ApplicationLifecycleManager, lifecycle_context
from backend.app.core.metadata import ApplicationMetadata
from backend.app.core.plugins import PluginRegistry
from backend.app.database.session import SessionLocal, initialize_database
from backend.app.evaluation.engine import EvaluationEngine
from backend.app.events.bus import EventBus
from backend.app.events.dispatcher import EventDispatcher
from backend.app.events.registry import EventHandlerRegistry
from backend.app.integrations.netbox.client import NetBoxClient
from backend.app.integrations.netbox.mapper import NetBoxInventoryMapper
from backend.app.integrations.netbox.service import NetBoxService
from backend.app.inventory.mapper import InventoryMapper
from backend.app.jobs.manager import JobManager
from backend.app.jobs.repository import InMemoryJobRepository
from backend.app.normalization.engine import NormalizationEngine
from backend.app.notifications.service import NotificationService
from backend.app.orchestration.coordinator import DiscoveryCoordinator
from backend.app.orchestration.engine import OrchestrationEngine
from backend.app.orchestration.workflow import WorkflowEngine
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.registry import ParserRegistry
from backend.app.persistence.unit_of_work import PersistenceUnitOfWork
from backend.app.scheduler.registry import WorkerRegistry
from backend.app.services.base import ServiceContext
from backend.app.services.inventory import InventoryService
from backend.app.snapshot.models import InventorySnapshotModel
from backend.app.transports.http.httpx import HttpxTransport
from backend.app.transports.manager import TransportManager
from backend.app.transports.snmp.pysnmp import PySnmpTransport
from backend.app.transports.ssh.netmiko import NetmikoSSHTransport
from backend.app.transports.ssh.paramiko import ParamikoSSHTransport


class _InMemorySnapshotRepository:
    """Minimal async snapshot repository for the collector runtime."""

    def __init__(self) -> None:
        self._snapshots: list[InventorySnapshotModel] = []

    async def save(self, snapshot: InventorySnapshotModel) -> None:
        self._snapshots.append(snapshot)

    async def get(self, snapshot_id: object) -> InventorySnapshotModel | None:
        for snapshot in self._snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        return None

    async def list(self) -> tuple[InventorySnapshotModel, ...]:
        return tuple(self._snapshots)

    async def delete(self, snapshot_id: object) -> None:
        self._snapshots = [
            snapshot
            for snapshot in self._snapshots
            if snapshot.snapshot_id != snapshot_id
        ]

    async def clear(self) -> None:
        self._snapshots.clear()


def _build_runtime_services(
    settings: Settings,
) -> tuple[InventoryService, CollectorRuntimeEngine, CollectorRegistry]:
    """Build the real NetBox inventory and collector runtime graph."""

    if not settings.netbox_url:
        raise ValueError(
            "NETBOX_URL configuration is missing or empty. A valid URL is required."
        )
    if not settings.netbox_expected_version:
        raise ValueError(
            "NETBOX_EXPECTED_VERSION configuration is missing or empty. A valid "
            "version is required."
        )

    settings.netbox_base_url = settings.netbox_url
    netbox_client = NetBoxClient.from_settings(
        settings,
        response_cache=None,
    )
    netbox_service = NetBoxService(client=netbox_client)
    inventory_service = InventoryService(
        context=ServiceContext(settings=settings),
        netbox_service=netbox_service,
        inventory_mapper=InventoryMapper(netbox_mapper=NetBoxInventoryMapper()),
        cache=build_cache_backend(settings.redis_url),
    )

    transport_manager = TransportManager()
    for transport in (
        NetmikoSSHTransport(),
        ParamikoSSHTransport(),
        PySnmpTransport(),
        HttpxTransport(),
    ):
        transport_manager.register(transport)

    parser_registry = ParserRegistry()
    parser_registry.register(CiscoInventoryParser())
    collector_registry = build_cisco_inventory_registry(transport_manager)
    collector_executor = CollectorExecutor(
        collector_registry=collector_registry,
        transport_manager=transport_manager,
        parser_pipeline=ParserPipeline(registry=parser_registry),
        normalization_engine=NormalizationEngine(),
        snapshot_repository=_InMemorySnapshotRepository(),
        metrics=CollectorRuntimeMetrics(),
    )
    runtime_metrics = collector_executor.metrics
    scheduler = CollectorScheduler()
    dispatcher = CollectorDispatcher(
        executor=collector_executor,
        scheduler=scheduler,
        metrics=runtime_metrics,
    )
    collector_runtime = CollectorRuntimeEngine(
        scheduler=scheduler,
        dispatcher=dispatcher,
        metrics=runtime_metrics,
    )
    return inventory_service, collector_runtime, collector_registry


@dataclass(slots=True)
class ApplicationContainer:
    """Compose framework services for dependency injection."""

    settings: Settings
    metadata: ApplicationMetadata
    plugins: PluginRegistry
    lifecycle: ApplicationLifecycleManager
    event_registry: EventHandlerRegistry
    event_dispatcher: EventDispatcher
    event_bus: EventBus
    notification_service: NotificationService
    engine: OrchestrationEngine
    repository: InMemoryJobRepository
    job_manager: JobManager
    worker_registry: WorkerRegistry
    discovery_collector_registry: CollectorRegistry


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
    initialize_database()

    lifecycle_manager = ApplicationLifecycleManager()
    event_registry = EventHandlerRegistry()
    event_dispatcher = EventDispatcher(event_registry)
    event_bus = EventBus(registry=event_registry)
    notification_service = NotificationService(adapters={}, mappings=[])
    inventory_service, collector_runtime, collector_registry = _build_runtime_services(
        app_settings
    )
    workflow = WorkflowEngine(
        inventory_service=inventory_service,
        discovery_coordinator=DiscoveryCoordinator(collector_runtime),
        comparison_engine=ComparisonEngine(),
        evaluation_engine=EvaluationEngine(),
        unit_of_work_factory=lambda: PersistenceUnitOfWork(SessionLocal()),
    )
    engine = OrchestrationEngine(workflow)
    repository = InMemoryJobRepository()
    job_manager = JobManager(
        engine=engine,
        repository=repository,
        event_publisher=event_bus,
        worker_count=1,
    )
    container = ApplicationContainer(
        settings=app_settings,
        metadata=metadata,
        plugins=PluginRegistry(),
        lifecycle=lifecycle_manager,
        event_registry=event_registry,
        event_dispatcher=event_dispatcher,
        event_bus=event_bus,
        notification_service=notification_service,
        engine=engine,
        repository=repository,
        job_manager=job_manager,
        worker_registry=WorkerRegistry(),
        discovery_collector_registry=collector_registry,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with lifecycle_context(container.lifecycle):
            from datetime import UTC, datetime

            from backend.app.database.session import SessionLocal
            from backend.app.persistence.models import NetBoxSyncJobRecord

            session = SessionLocal()
            try:
                stuck_jobs = (
                    session.query(NetBoxSyncJobRecord)
                    .filter(NetBoxSyncJobRecord.status.in_(["queued", "running"]))
                    .all()
                )
                for job in stuck_jobs:
                    job.status = "failed"
                    job.finished_at = datetime.now(UTC)
                    job.error_message = "System restarted during synchronization."
                session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()
            yield

    app = FastAPI(
        title=metadata.name,
        version=metadata.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
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

    from backend.app.api.v1.exceptions import NetBoxIntegrationError

    @app.exception_handler(NetBoxIntegrationError)
    async def handle_netbox_integration_error(
        request: Request,
        exc: NetBoxIntegrationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
            status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
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
