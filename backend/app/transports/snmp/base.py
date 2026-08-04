"""SNMP transport abstraction."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from backend.app.transports.base import BaseTransport, TransportCapability


@dataclass(slots=True)
class SNMPTransport(BaseTransport, ABC):
    """Abstract SNMP transport base class."""

    capabilities: frozenset[TransportCapability] = frozenset({TransportCapability.SNMP})
