"""Reusable network transport framework."""

from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
    TransportTarget,
)
from backend.app.transports.circuit_breaker import CircuitBreaker, CircuitBreakerState
from backend.app.transports.connection_pool import ConnectionPool
from backend.app.transports.credentials import (
    CredentialResolver,
    MappingCredentialResolver,
    StaticCredentialResolver,
    TokenCredentials,
    TransportCredentials,
    UsernamePasswordCredentials,
)
from backend.app.transports.manager import TransportManager
from backend.app.transports.rate_limiter import RateLimiter
from backend.app.transports.registry import TransportRegistry
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.session import TransportSession
from backend.app.transports.timeout import TransportTimeout

__all__ = [
    "BaseTransport",
    "CircuitBreaker",
    "CircuitBreakerState",
    "ConnectionPool",
    "CredentialResolver",
    "MappingCredentialResolver",
    "RateLimiter",
    "StaticCredentialResolver",
    "TokenCredentials",
    "TransportCapability",
    "TransportContext",
    "TransportCredentials",
    "TransportManager",
    "TransportRegistry",
    "TransportRetryPolicy",
    "TransportSession",
    "TransportTarget",
    "TransportTimeout",
    "UsernamePasswordCredentials",
]
