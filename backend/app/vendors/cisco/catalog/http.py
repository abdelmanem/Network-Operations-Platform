"""Cisco HTTP catalogs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class HttpMethod(StrEnum):
    """HTTP methods used in Cisco endpoint metadata."""

    GET = "GET"


@dataclass(frozen=True, slots=True)
class HttpEndpointMetadata:
    """Describe a Cisco HTTP endpoint without issuing requests."""

    method: HttpMethod
    path: str
    description: str


@dataclass(frozen=True, slots=True)
class HttpCatalog:
    """Immutable Cisco HTTP endpoint catalog."""

    endpoints: tuple[HttpEndpointMetadata, ...] = field(default_factory=tuple)

    def paths(self) -> tuple[str, ...]:
        """Return endpoint paths."""

        return tuple(endpoint.path for endpoint in self.endpoints)


COMMON_HTTP_CATALOG = HttpCatalog(
    endpoints=(
        HttpEndpointMetadata(
            method=HttpMethod.GET,
            path="/",
            description="Root banner endpoint.",
        ),
        HttpEndpointMetadata(
            method=HttpMethod.GET,
            path="/status",
            description="Device status endpoint.",
        ),
    )
)


def build_common_http_catalog() -> HttpCatalog:
    """Return the shared Cisco HTTP catalog."""

    return COMMON_HTTP_CATALOG
