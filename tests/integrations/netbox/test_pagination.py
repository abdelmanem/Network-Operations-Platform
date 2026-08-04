from typing import Any

import pytest
from backend.app.integrations.netbox.models import (
    NetBoxCollectionResponse,
    NetBoxSite,
)
from backend.app.integrations.netbox.pagination import (
    NetBoxPaginator,
    PaginationOptions,
)


@pytest.mark.anyio
async def test_paginator_streams_pages_and_progress() -> None:
    pages = [
        {
            "count": 3,
            "next": "https://netbox.example.com/api/dcim/sites/?limit=2&page=2",
            "previous": None,
            "results": [
                {"id": 1, "name": "Site A", "slug": "site-a"},
                {"id": 2, "name": "Site B", "slug": "site-b"},
            ],
        },
        {
            "count": 3,
            "next": None,
            "previous": "https://netbox.example.com/api/dcim/sites/?limit=2",
            "results": [{"id": 3, "name": "Site C", "slug": "site-c"}],
        },
    ]
    progress: list[tuple[int, int | None]] = []

    async def fetch_page(
        endpoint: str, params: dict[str, Any] | None
    ) -> NetBoxCollectionResponse[Any]:
        return NetBoxCollectionResponse[Any].model_validate(pages.pop(0))

    paginator = NetBoxPaginator(
        fetch_page,
        options=PaginationOptions(
            page_size=2,
            progress_callback=lambda retrieved, total: progress.append(
                (retrieved, total)
            ),
        ),
    )

    results = [
        item async for item in paginator.iter_results("/api/dcim/sites/", NetBoxSite)
    ]

    assert [result.name for result in results] == ["Site A", "Site B", "Site C"]
    assert progress[-1] == (3, 3)
