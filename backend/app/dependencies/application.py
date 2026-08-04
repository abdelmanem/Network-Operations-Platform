"""Application-scoped dependencies."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from backend.app.core.application import ApplicationContainer
from backend.app.core.exceptions import DependencyError


def get_application_container(request: Request) -> ApplicationContainer:
    """Return the application container from request state."""

    container = getattr(request.app.state, "container", None)
    if container is None:
        raise DependencyError("Application container is not available.")
    return cast(ApplicationContainer, container)
