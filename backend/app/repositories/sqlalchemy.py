"""SQLAlchemy repository base implementation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.repositories.interfaces import SupportsUUIDIdentity


@dataclass(slots=True)
class SQLAlchemyRepository[TModel: SupportsUUIDIdentity]:
    """Base repository backed by a SQLAlchemy session."""

    session: Session
    model_type: type[TModel]

    def add(self, item: TModel) -> TModel:
        """Add an item to the repository."""

        self.session.add(item)
        return item

    def get(self, identity: UUID) -> TModel | None:
        """Return an item by identifier."""

        return self.session.get(self.model_type, identity)

    def list(self) -> tuple[TModel, ...]:
        """Return all items in the repository."""

        statement = select(self.model_type)
        return tuple(self.session.scalars(statement).all())

    def remove(self, item: TModel) -> None:
        """Remove an item from the repository."""

        self.session.delete(item)
