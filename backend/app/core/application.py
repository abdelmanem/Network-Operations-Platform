"""Application factory and runtime container."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from backend.app.api.router import api_router
from backend.app.config.logging import configure_logging
from backend.app.config.settings import Settings, get_settings
from backend.app.core.constants import APP_NAME, APP_PACKAGE, APP_VERSION
from backend.app.core.lifecycle import ApplicationLifecycleManager, lifecycle_context
from backend.app.core.metadata import ApplicationMetadata
from backend.app.core.plugins import PluginRegistry
from backend.app.events.dispatcher import EventDispatcher
from backend.app.events.registry import EventHandlerRegistry


@dataclass(slots=True)
class ApplicationContainer:
    """Compose framework services for dependency injection."""

    settings: Settings
    metadata: ApplicationMetadata
    plugins: PluginRegistry
    lifecycle: ApplicationLifecycleManager
    event_registry: EventHandlerRegistry
    event_dispatcher: EventDispatcher


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
    container = ApplicationContainer(
        settings=app_settings,
        metadata=metadata,
        plugins=PluginRegistry(),
        lifecycle=lifecycle_manager,
        event_registry=event_registry,
        event_dispatcher=event_dispatcher,
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
    app.state.container = container
    app.include_router(api_router)
    return app
