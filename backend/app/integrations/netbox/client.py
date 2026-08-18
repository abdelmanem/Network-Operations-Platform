"""Reusable NetBox REST client built on httpx."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, cast

import httpx

from backend.app.integrations.netbox.authentication import (
    NetBoxAuthentication,
    build_authentication,
)
from backend.app.integrations.netbox.cache import NetBoxResponseCache
from backend.app.integrations.netbox.endpoints import NetBoxEndpoint
from backend.app.integrations.netbox.exceptions import (
    NetBoxConfigurationError,
    NetBoxRateLimitError,
    NetBoxResponseError,
    NetBoxTransportError,
    NetBoxValidationError,
)
from backend.app.integrations.netbox.models import (
    NetBoxCollectionResponse,
    NetBoxModel,
    NetBoxStatusResponse,
)
from backend.app.integrations.netbox.pagination import (
    NetBoxPaginator,
    PaginationOptions,
)
from backend.app.integrations.netbox.retry import RetryPolicy
from backend.app.inventory.validation import (
    validate_collection_payload,
    validate_version,
)

TNetBoxModel = TypeVar("TNetBoxModel", bound=NetBoxModel)


class NetBoxSettings(Protocol):
    """Settings values required by the NetBox client."""

    netbox_base_url: str
    netbox_token: str
    netbox_timeout_seconds: float
    netbox_retry_max_attempts: int
    netbox_retry_base_delay_seconds: float
    netbox_page_size: int
    netbox_expected_version: str
    netbox_ca_cert: str


@dataclass(slots=True)
class NetBoxClient:
    """High-level NetBox API client."""

    base_url: str
    authentication: NetBoxAuthentication | None = None
    timeout_seconds: float = 10.0
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    page_size: int = 100
    expected_version: str | None = None
    response_cache: NetBoxResponseCache | None = None
    transport: httpx.AsyncBaseTransport | None = None
    ca_cert: str | None = None
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("backend.app.integrations.netbox")
    )
    _client: httpx.AsyncClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.base_url:
            raise NetBoxConfigurationError("NetBox base URL is required.")

        normalized_base_url = self.base_url.rstrip("/") + "/"
        headers = {"Accept": "application/json"}
        if self.authentication is not None:
            headers.update(self.authentication.build_headers())

        # Determine TLS verification strategy
        # If ca_cert is provided, use it; otherwise use system default trust store
        verify: bool | str = True
        if self.ca_cert:
            verify = self.ca_cert

        self._client = httpx.AsyncClient(
            base_url=normalized_base_url,
            headers=headers,
            timeout=httpx.Timeout(self.timeout_seconds),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            transport=self.transport,
            follow_redirects=True,
            verify=verify,
        )

    @classmethod
    def from_settings(
        cls,
        settings: NetBoxSettings,
        *,
        response_cache: NetBoxResponseCache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> NetBoxClient:
        """Create a NetBox client from application settings."""

        authentication = build_authentication(
            token=getattr(settings, "netbox_token", None)
        )
        ca_cert = getattr(settings, "netbox_ca_cert", "") or None
        if ca_cert:
            from pathlib import Path

            cert_path = Path(ca_cert)
            if not cert_path.is_absolute():
                project_root = Path(__file__).resolve().parents[4]
                ca_cert = str(project_root / cert_path)

        return cls(
            base_url=getattr(settings, "netbox_base_url", ""),
            authentication=authentication,
            timeout_seconds=getattr(settings, "netbox_timeout_seconds", 10.0),
            retry_policy=RetryPolicy(
                max_attempts=getattr(settings, "netbox_retry_max_attempts", 4),
                base_delay_seconds=getattr(
                    settings, "netbox_retry_base_delay_seconds", 0.5
                ),
            ),
            page_size=getattr(settings, "netbox_page_size", 100),
            expected_version=getattr(settings, "netbox_expected_version", None),
            response_cache=response_cache,
            transport=transport,
            ca_cert=ca_cert,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""

        await self._client.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, object] | None = None,
        json_body: object | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Send a request with retry handling and exception translation."""

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=cast(Any, params),
                    json=json_body,
                    headers=headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.retry_policy.max_attempts:
                    raise NetBoxTransportError(str(exc)) from exc
                await asyncio.sleep(self.retry_policy.delay_for_attempt(attempt))
                continue

            if response.status_code == 429:
                retry_after = self._parse_retry_after(
                    response.headers.get("Retry-After")
                )
                if attempt >= self.retry_policy.max_attempts:
                    raise NetBoxRateLimitError("NetBox rate limit exhausted.")
                await asyncio.sleep(
                    self.retry_policy.delay_for_attempt(
                        attempt,
                        retry_after_seconds=retry_after,
                    )
                )
                continue

            if self.retry_policy.should_retry(response.status_code):
                if attempt >= self.retry_policy.max_attempts:
                    raise self._build_response_error(response)
                await asyncio.sleep(self.retry_policy.delay_for_attempt(attempt))
                continue

            if response.is_error:
                raise self._build_response_error(response)

            return response

        raise NetBoxTransportError("NetBox request failed unexpectedly.")

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        """Parse the Retry-After header."""

        if value is None:
            return None

        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _build_response_error(response: httpx.Response) -> NetBoxResponseError:
        """Translate a failed HTTP response into a NetBox exception."""

        endpoint = str(response.request.url)
        detail = response.reason_phrase or "Unexpected NetBox response"
        return NetBoxResponseError(
            status_code=response.status_code,
            endpoint=endpoint,
            detail=detail,
            response_text=response.text,
        )

    async def request_json(
        self,
        method: str,
        endpoint: NetBoxEndpoint | str,
        *,
        params: dict[str, object] | None = None,
        json_body: object | None = None,
        cache_key: str | None = None,
        cache_ttl_seconds: int | None = None,
    ) -> object:
        """Send a request and return the JSON payload."""

        if (
            method.upper() == "GET"
            and cache_key is not None
            and self.response_cache is not None
        ):
            assert self.response_cache is not None
            cached = await self.response_cache.get_json(cache_key)
            if cached is not None:
                return cached

        response = await self._request(
            method.upper(),
            str(endpoint),
            params=params,
            headers={"Accept": "application/json"},
            json_body=json_body,
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise NetBoxValidationError("NetBox returned invalid JSON.") from exc

        if (
            method.upper() == "GET"
            and cache_key is not None
            and isinstance(payload, dict)
            and self.response_cache is not None
        ):
            assert self.response_cache is not None
            await self.response_cache.set_json(
                cache_key,
                payload,
                ttl_seconds=cache_ttl_seconds,
            )

        return payload

    async def fetch_page(
        self,
        endpoint: NetBoxEndpoint | str,
        params: dict[str, object] | None = None,
    ) -> NetBoxCollectionResponse[Any]:
        """Return a validated NetBox collection page."""

        payload = await self.request_json("GET", endpoint, params=params)
        validated_payload = validate_collection_payload(
            payload,
            context=f"{endpoint} collection",
        )
        return NetBoxCollectionResponse[Any].model_validate(validated_payload)

    async def list_collection(
        self,
        endpoint: NetBoxEndpoint | str,
        model_type: type[TNetBoxModel],
        *,
        params: dict[str, object] | None = None,
        progress_callback: Callable[[int, int | None], None] | None = None,
    ) -> tuple[TNetBoxModel, ...]:
        """Return a fully materialized collection."""

        paginator = NetBoxPaginator(
            self.fetch_page,
            options=PaginationOptions(
                page_size=self.page_size,
                progress_callback=progress_callback,
            ),
        )
        items = [
            item
            async for item in paginator.iter_results(
                str(endpoint), model_type, params=params
            )
        ]
        return tuple(items)

    async def health(self) -> NetBoxStatusResponse:
        """Return the NetBox health/status response."""

        cache_key = None
        if self.response_cache is not None:
            assert self.response_cache is not None
            cache_key = self.response_cache.keys.health()
            cached = await self.response_cache.get_json(cache_key)
            if cached is not None:
                health = NetBoxStatusResponse.model_validate(cached)
                self._validate_version(health)
                return health

        response = await self._request("GET", str(NetBoxEndpoint.STATUS))
        try:
            payload = response.json()
        except ValueError as exc:
            raise NetBoxValidationError(
                "NetBox status response was not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise NetBoxValidationError("NetBox status response must be a JSON object.")

        if cache_key is not None:
            assert self.response_cache is not None
            await self.response_cache.set_json(
                cache_key,
                payload,
                ttl_seconds=60,
            )

        health = NetBoxStatusResponse.model_validate(payload)
        health = health.model_copy(
            update={"api_version": response.headers.get("API-Version")}
        )
        self._validate_version(health)
        return health

    def _validate_version(self, health: NetBoxStatusResponse) -> None:
        """Validate the detected NetBox version if one is configured."""

        if self.expected_version is None:
            return

        actual_version = health.version or health.api_version
        validate_version(
            self.expected_version,
            actual_version,
            context="NetBox health check",
        )
