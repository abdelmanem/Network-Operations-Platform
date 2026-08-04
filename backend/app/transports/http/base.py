"""HTTP transport abstraction."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from backend.app.transports.base import BaseTransport, TransportCapability


@dataclass(slots=True)
class HTTPTransport(BaseTransport, ABC):
    """Abstract HTTP transport base class."""

    capabilities: frozenset[TransportCapability] = frozenset({TransportCapability.HTTP})
