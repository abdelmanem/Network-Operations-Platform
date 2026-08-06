from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, cast

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.database.session import get_db_session as db_session_dependency
from backend.app.jobs.manager import JobManager

if TYPE_CHECKING:
    from backend.app.core.application import ApplicationContainer


def get_application_container(request: Request) -> ApplicationContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("Application container not available")
    return cast("ApplicationContainer", container)


def get_job_manager(request: Request) -> JobManager:
    return get_application_container(request).job_manager


def get_db_session() -> Generator[Session, None, None]:
    yield from db_session_dependency()
