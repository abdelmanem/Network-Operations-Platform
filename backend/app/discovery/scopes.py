"""Discovery scope expansion primitives."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network

from backend.app.discovery.contracts import DiscoveryScopeType


class DiscoveryScopeError(ValueError):
    """Raised when a scope cannot be expanded safely."""


@dataclass(frozen=True, slots=True)
class DiscoveryScope:
    """MVP scope definition for single devices, ranges, and CIDR networks."""

    scope_type: DiscoveryScopeType
    address: str | None = None
    scope_end: str | None = None
    scope_cidr: str | None = None

    def expand(self, *, max_targets: int = 4096) -> tuple[str, ...]:
        """Expand the scope into bounded individual management addresses."""

        if max_targets < 1:
            raise DiscoveryScopeError("Maximum target count must be positive.")
        if self.scope_type == DiscoveryScopeType.SINGLE_DEVICE:
            if self.address is None:
                raise DiscoveryScopeError("Single-device address is required.")
            ip_address(self.address)
            return (self.address,)
        if self.scope_type == DiscoveryScopeType.IP_RANGE:
            if self.address is None or self.scope_end is None:
                raise DiscoveryScopeError("IP range boundaries are required.")
            start = ip_address(self.address)
            end = ip_address(self.scope_end)
            if start.version != end.version or int(start) > int(end):
                raise DiscoveryScopeError("IP range boundaries are invalid.")
            count = int(end) - int(start) + 1
            if count > max_targets:
                raise DiscoveryScopeError("IP range exceeds the target limit.")
            return tuple(str(start + offset) for offset in range(count))
        if self.scope_type == DiscoveryScopeType.CIDR_NETWORK:
            if self.scope_cidr is None:
                raise DiscoveryScopeError("CIDR network is required.")
            network = ip_network(self.scope_cidr, strict=False)
            hosts = tuple(network.hosts())
            if len(hosts) > max_targets:
                raise DiscoveryScopeError("CIDR network exceeds the target limit.")
            return tuple(str(host) for host in hosts)
        raise DiscoveryScopeError("This discovery scope is not executable yet.")


__all__ = ["DiscoveryScope", "DiscoveryScopeError"]
