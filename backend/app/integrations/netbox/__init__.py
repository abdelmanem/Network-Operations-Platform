"""NetBox integration boundary."""

from backend.app.integrations.netbox.authentication import (
    OAuthAuthentication,
    TokenAuthentication,
)
from backend.app.integrations.netbox.client import NetBoxClient
from backend.app.integrations.netbox.endpoints import NetBoxEndpoint
from backend.app.integrations.netbox.exceptions import (
    NetBoxAuthenticationError,
    NetBoxCacheError,
    NetBoxConfigurationError,
    NetBoxError,
    NetBoxRateLimitError,
    NetBoxResponseError,
    NetBoxTransportError,
    NetBoxValidationError,
    NetBoxVersionMismatchError,
)

__all__ = [
    "NetBoxAuthenticationError",
    "NetBoxCacheError",
    "NetBoxClient",
    "NetBoxConfigurationError",
    "NetBoxEndpoint",
    "NetBoxError",
    "NetBoxRateLimitError",
    "NetBoxResponseError",
    "NetBoxTransportError",
    "NetBoxValidationError",
    "NetBoxVersionMismatchError",
    "OAuthAuthentication",
    "TokenAuthentication",
]
