"""Base service class and dependency support."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.app.config.settings import Settings
from backend.app.events.interfaces import EventPublisher


@dataclass(slots=True)
class ServiceContext:
    """Dependencies shared by services."""

    settings: Settings
    event_publisher: EventPublisher | None = None
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("backend.app.services")
    )


@dataclass(slots=True)
class BaseService:
    """Base class for application services."""

    context: ServiceContext

    @property
    def settings(self) -> Settings:
        """Return configured application settings."""

        return self.context.settings

    @property
    def logger(self) -> logging.Logger:
        """Return the service logger."""

        return self.context.logger

    @property
    def event_publisher(self) -> EventPublisher | None:
        """Return the configured event publisher."""

        return self.context.event_publisher
