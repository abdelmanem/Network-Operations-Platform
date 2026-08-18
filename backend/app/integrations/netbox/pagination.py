"""Pagination helpers for NetBox list endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from backend.app.integrations.netbox.endpoints import NetBoxEndpoint
from backend.app.integrations.netbox.models import (
    NetBoxCollectionResponse,
    NetBoxModel,
)

PageFetcher = Callable[
    [NetBoxEndpoint | str, dict[str, object] | None],
    Awaitable[NetBoxCollectionResponse[Any]],
]
ProgressCallback = Callable[[int, int | None], None]


@dataclass(frozen=True, slots=True)
class PaginationOptions:
    """Pagination parameters for NetBox collection requests."""

    page_size: int = 100
    progress_callback: ProgressCallback | None = None


class NetBoxPaginator:
    """Stream paginated NetBox records."""

    def __init__(
        self,
        fetch_page: PageFetcher,
        *,
        options: PaginationOptions | None = None,
    ) -> None:
        self._fetch_page = fetch_page
        self._options = options or PaginationOptions()

    async def iter_pages(
        self,
        endpoint: NetBoxEndpoint | str,
        *,
        params: dict[str, object] | None = None,
    ) -> AsyncIterator[NetBoxCollectionResponse[Any]]:
        """Iterate over paginated responses."""

        request_params: dict[str, object] | None = dict(params or {})
        if request_params is not None:
            request_params["limit"] = self._options.page_size
        current_endpoint = endpoint

        while True:
            page = await self._fetch_page(current_endpoint, request_params)
            yield page

            next_url = page.next
            if next_url is None:
                return

            current_endpoint = next_url
            request_params = None

    async def iter_results[TNetBoxModel: NetBoxModel](
        self,
        endpoint: NetBoxEndpoint | str,
        model_type: type[TNetBoxModel],
        *,
        params: dict[str, object] | None = None,
    ) -> AsyncIterator[TNetBoxModel]:
        """Iterate over individual results across all pages."""

        retrieved = 0
        page_count: int | None = None
        async for page in self.iter_pages(endpoint, params=params):
            page_count = page.count
            for result in page.results:
                retrieved += 1
                if self._options.progress_callback is not None:
                    self._options.progress_callback(retrieved, page_count)
                yield model_type.model_validate(result)
