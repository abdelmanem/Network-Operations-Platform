from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error envelope for API operations."""

    detail: str
    error: str | None = None


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class PaginatedResponse[TItem](BaseModel):
    """Generic paginated response envelope."""

    items: list[TItem]
    page: int
    page_size: int
    total: int
    has_next: bool
