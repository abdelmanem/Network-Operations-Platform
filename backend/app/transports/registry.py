"""Transport registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from backend.app.transports.base import BaseTransport, TransportCapability
from backend.app.transports.exceptions import TransportUnavailableError

TransportFactory = Callable[[], BaseTransport]


@dataclass(slots=True)
class TransportRegistry:
    """Register and resolve transport implementations."""

    _transports: dict[str, BaseTransport] = field(default_factory=dict)

    def register(self, transport: BaseTransport | TransportFactory) -> None:
        """Register a transport instance or factory."""

        if isinstance(transport, BaseTransport):
            self._transports[transport.name] = transport
            return

        instance = transport()
        self._transports[instance.name] = instance

    def get(self, name: str) -> BaseTransport:
        """Return a transport by name."""

        try:
            return self._transports[name]
        except KeyError as exc:
            raise TransportUnavailableError(f"Unknown transport: {name}") from exc

    def select(
        self, capabilities: frozenset[TransportCapability]
    ) -> tuple[BaseTransport, ...]:
        """Return transports that satisfy the requested capabilities."""

        return tuple(
            transport
            for transport in self._transports.values()
            if capabilities.issubset(transport.capabilities)
        )

    def names(self) -> tuple[str, ...]:
        """Return registered transport names."""

        return tuple(self._transports)
