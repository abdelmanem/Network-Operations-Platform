"""SQLAlchemy declarative base."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class BaseModel(DeclarativeBase):
    """Base declarative model."""
