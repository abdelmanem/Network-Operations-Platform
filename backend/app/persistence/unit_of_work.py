"""Unit-of-work integration for immutable history persistence."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.app.core.exceptions import TransactionError
from backend.app.persistence.repositories import (
    FindingRepository,
    HistoryRepository,
    SnapshotRepository,
)


@dataclass(slots=True)
class PersistenceUnitOfWork:
    """Unit of work exposing persistence repositories."""

    session: Session
    _committed: bool = False
    history: HistoryRepository = field(init=False)
    snapshots: SnapshotRepository = field(init=False)
    findings: FindingRepository = field(init=False)

    def __post_init__(self) -> None:
        self.history = HistoryRepository(self.session)
        self.snapshots = SnapshotRepository(self.session)
        self.findings = FindingRepository(self.session)

    def __enter__(self) -> PersistenceUnitOfWork:
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
            raise TransactionError(
                "Failed to commit persistence unit of work."
            ) from exc

    def rollback(self) -> None:
        """Rollback the session transaction."""

        try:
            self.session.rollback()
        except Exception as exc:  # pragma: no cover - defensive guard
            raise TransactionError(
                "Failed to rollback persistence unit of work."
            ) from exc
