"""Unit-of-work foundation."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.core.exceptions import TransactionError


class UnitOfWork:
    """Protocol-like base for unit-of-work implementations."""

    session: Session

    def commit(self) -> None:
        """Commit the current unit of work."""

        raise NotImplementedError

    def rollback(self) -> None:
        """Rollback the current unit of work."""

        raise NotImplementedError


@dataclass(slots=True)
class SQLAlchemyUnitOfWork(UnitOfWork):
    """Context-managed SQLAlchemy unit of work."""

    session: Session
    _committed: bool = False

    def __enter__(self) -> SQLAlchemyUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if exc is not None:
            self.rollback()
            return

        if not self._committed:
            self.commit()

    def commit(self) -> None:
        """Commit the session transaction."""

        try:
            self.session.commit()
            self._committed = True
        except Exception as exc:  # pragma: no cover - defensive guard
            raise TransactionError("Failed to commit unit of work.") from exc

    def rollback(self) -> None:
        """Rollback the session transaction."""

        try:
            self.session.rollback()
        except Exception as exc:  # pragma: no cover - defensive guard
            raise TransactionError("Failed to rollback unit of work.") from exc
