"""Repository abstractions and implementations."""

from backend.app.repositories.interfaces import GenericRepository
from backend.app.repositories.sqlalchemy import SQLAlchemyRepository
from backend.app.repositories.transaction import TransactionManager
from backend.app.repositories.unit_of_work import SQLAlchemyUnitOfWork, UnitOfWork

__all__ = [
    "GenericRepository",
    "SQLAlchemyRepository",
    "SQLAlchemyUnitOfWork",
    "TransactionManager",
    "UnitOfWork",
]
