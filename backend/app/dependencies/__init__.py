"""Dependency injection entry points."""

from backend.app.dependencies.database import get_db_session
from backend.app.dependencies.settings import get_settings

__all__ = [
    "get_db_session",
    "get_settings",
]
