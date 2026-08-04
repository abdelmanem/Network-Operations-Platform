"""Transaction abstraction."""

from __future__ import annotations

from typing import Protocol


class TransactionManager(Protocol):
    """Protocol for transaction managers."""

    def commit(self) -> None:
        """Commit the active transaction."""

    def rollback(self) -> None:
        """Rollback the active transaction."""
