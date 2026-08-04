"""Transport manager."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.transports.base import (
    BaseTransport,
    TransportCapability,
    TransportContext,
    TransportTarget,
)
from backend.app.transports.circuit_breaker import CircuitBreaker
from backend.app.transports.connection_pool import ConnectionPool
from backend.app.transports.credentials import (
    CredentialResolver,
    TransportCredentials,
)
from backend.app.transports.rate_limiter import RateLimiter
from backend.app.transports.registry import TransportRegistry
from backend.app.transports.retry import TransportRetryPolicy
from backend.app.transports.session import TransportSession
from backend.app.transports.timeout import TransportTimeout


@dataclass(slots=True)
class TransportManager:
    """Coordinate transport resolution, pooling, and lifecycle."""

    registry: TransportRegistry = field(default_factory=TransportRegistry)
    pool: ConnectionPool = field(default_factory=ConnectionPool)
    credential_resolver: CredentialResolver | None = None
    retry_policy: TransportRetryPolicy = field(default_factory=TransportRetryPolicy)
    timeout: TransportTimeout = field(default_factory=TransportTimeout)
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    rate_limiter: RateLimiter | None = None

    def register(self, transport: BaseTransport) -> None:
        """Register a transport implementation."""

        self.registry.register(transport)

    def resolve(self, name: str) -> BaseTransport:
        """Resolve a transport by name."""

        return self.registry.get(name)

    def select(
        self,
        capabilities: frozenset[TransportCapability],
    ) -> tuple[BaseTransport, ...]:
        """Return transports that support the requested capabilities."""

        return self.registry.select(capabilities)

    async def open_session(
        self,
        transport_name: str,
        target: TransportTarget,
        *,
        capabilities: frozenset[TransportCapability] | None = None,
    ) -> TransportSession:
        """Open or reuse a transport session."""

        if not self.circuit_breaker.allow_request():
            raise RuntimeError("Transport circuit breaker is open.")

        if self.rate_limiter is not None:
            await self.rate_limiter.acquire()

        transport = self.resolve(transport_name)
        context = self.build_context(
            target,
            capabilities=capabilities or transport.capabilities,
        )
        try:
            transport.health_check(context)
            session = await self.pool.get_or_create(
                self._pool_key(transport_name, target.identifier),
                lambda: transport.create_session(context),
            )
        except Exception:
            self.circuit_breaker.record_failure()
            raise

        self.circuit_breaker.record_success()
        return session

    async def close_session(self, transport_name: str, target: TransportTarget) -> None:
        """Close a pooled session."""

        await self.pool.release(self._pool_key(transport_name, target.identifier))

    async def close_all(self) -> None:
        """Close all pooled sessions."""

        await self.pool.close_all()

    def build_context(
        self,
        target: TransportTarget,
        *,
        capabilities: frozenset[TransportCapability],
    ) -> TransportContext:
        """Build a transport execution context."""

        credentials = self.resolve_credentials(target, capabilities=capabilities)
        return TransportContext(
            target=target,
            capabilities=capabilities,
            credentials=credentials,
            timeout=self.timeout,
            retry_policy=self.retry_policy,
        )

    def resolve_credentials(
        self,
        target: TransportTarget,
        *,
        capabilities: frozenset[TransportCapability],
    ) -> TransportCredentials | None:
        """Resolve credentials for a transport target."""

        if self.credential_resolver is None:
            return None

        context = TransportContext(target=target, capabilities=capabilities)
        return self.credential_resolver.resolve(context)

    @staticmethod
    def _pool_key(transport_name: str, target_identifier: str) -> str:
        return f"{transport_name}:{target_identifier}"
