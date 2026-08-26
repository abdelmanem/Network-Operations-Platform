"""Service reachability probing for discovery transports.

This module provides lightweight service detection capabilities for network
discovery operations. It performs targeted TCP/UDP connection attempts to
determine which management services may be available on target devices.

Key principles:
- No aggressive port scanning
- Only probe configured management transports
- Lightweight timeout-based checks
- Results inform transport priority, not filter targets
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.transports.base import TransportCapability


class TransportService(StrEnum):
    """Standard network management service identifiers."""

    SSH = "ssh"
    TELNET = "telnet"
    HTTP = "http"
    HTTPS = "https"
    SNMP = "snmp"


# Standard port mappings for management services
TRANSPORT_PORTS: dict[TransportService, int] = {
    TransportService.SSH: 22,
    TransportService.TELNET: 23,
    TransportService.HTTP: 80,
    TransportService.HTTPS: 443,
    TransportService.SNMP: 161,
}

# Transport capability to service mapping
CAPABILITY_TO_SERVICE: dict[str, TransportService] = {
    "SSH": TransportService.SSH,
    "TELNET": TransportService.TELNET,
    "HTTP": TransportService.HTTP,
    "HTTPS": TransportService.HTTPS,
    "SNMP": TransportService.SNMP,
}


def get_service_for_capability(capability: object) -> TransportService | None:
    """Resolve the TransportService for a given TransportCapability value.

    Args:
        capability: A TransportCapability enum value or string

    Returns:
        Corresponding TransportService or None if not mapped
    """
    from backend.app.transports.base import TransportCapability

    if isinstance(capability, TransportCapability):
        key = capability.value
    else:
        key = str(capability).upper()
    return CAPABILITY_TO_SERVICE.get(key)


@dataclass(frozen=True, slots=True)
class ServiceProbeResult:
    """Result of a single service probe attempt."""

    service: TransportService
    address: str
    port: int
    is_available: bool
    response_time_ms: float
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class HostProbeResult:
    """Combined probe results for a single host."""

    address: str
    services: dict[TransportService, ServiceProbeResult] = field(default_factory=dict)
    is_reachable: bool = False

    def get_available_services(self) -> list[TransportService]:
        """Return list of services that responded positively."""
        return [
            service
            for service, result in self.services.items()
            if result.is_available
        ]

    def is_service_available(self, service: TransportService) -> bool:
        """Check if a specific service is available."""
        result = self.services.get(service)
        return result.is_available if result else False


class ServiceProber:
    """Lightweight service detection for discovery transports.

    Performs targeted TCP/UDP connection attempts to determine
    which management services may be available on target devices.
    """

    def __init__(
        self,
        *,
        default_timeout_seconds: float = 5.0,
        concurrent_limit: int = 50,
    ) -> None:
        self.default_timeout = default_timeout_seconds
        self.concurrent_limit = concurrent_limit

    async def probe_host(
        self,
        address: str,
        services: list[TransportService],
        *,
        timeout_seconds: float | None = None,
    ) -> HostProbeResult:
        """Probe a single host for available management services.

        Args:
            address: IP address or hostname to probe
            services: List of services to check
            timeout_seconds: Override default timeout

        Returns:
            HostProbeResult with availability status for each service
        """
        timeout = timeout_seconds or self.default_timeout
        result = HostProbeResult(address=address, services={})

        # Probe each service concurrently with semaphore limit
        semaphore = asyncio.Semaphore(self.concurrent_limit)

        async def probe_with_limit(service: TransportService) -> ServiceProbeResult:
            async with semaphore:
                return await self._probe_single_service(address, service, timeout)

        # Execute all probes concurrently
        probe_tasks = [probe_with_limit(service) for service in services]
        probe_results = await asyncio.gather(*probe_tasks, return_exceptions=True)

        # Process results
        any_reachable = False
        for service, probe_result in zip(services, probe_results):
            if isinstance(probe_result, Exception):
                # Create failed result for exception case
                failed_result = ServiceProbeResult(
                    service=service,
                    address=address,
                    port=TRANSPORT_PORTS.get(service, 0),
                    is_available=False,
                    response_time_ms=0.0,
                    error_message=str(probe_result),
                )
                result.services[service] = failed_result
            else:
                result.services[service] = probe_result
                if probe_result.is_available:
                    any_reachable = True

        # Host is reachable if any service responded or if we got any TCP response
        result.is_reachable = any_reachable or len(result.services) > 0

        return result

    async def probe_hosts(
        self,
        addresses: list[str],
        services: list[TransportService],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, HostProbeResult]:
        """Probe multiple hosts concurrently for available services.

        Args:
            addresses: List of IP addresses or hostnames to probe
            services: List of services to check on each host
            timeout_seconds: Override default timeout

        Returns:
            Dictionary mapping address to HostProbeResult
        """
        results: dict[str, HostProbeResult] = {}

        # Use semaphore to limit concurrent probes across all hosts
        semaphore = asyncio.Semaphore(self.concurrent_limit)
        timeout = timeout_seconds or self.default_timeout

        async def probe_single_host(address: str) -> tuple[str, HostProbeResult]:
            async with semaphore:
                result = await self.probe_host(address, services, timeout_seconds=timeout)
                return address, result

        # Probe all hosts concurrently
        probe_tasks = [probe_single_host(address) for address in addresses]
        probe_results = await asyncio.gather(probe_tasks, return_exceptions=True)

        for item in probe_results:
            if isinstance(item, Exception):
                # Log exception but continue with other results
                continue
            address, result = item
            results[address] = result

        return results

    async def _probe_single_service(
        self,
        address: str,
        service: TransportService,
        timeout: float,
    ) -> ServiceProbeResult:
        """Probe a single service on a host.

        Performs a lightweight TCP or UDP connection attempt to determine
        if the service is available.
        """
        import time

        port = TRANSPORT_PORTS.get(service)
        if port is None:
            return ServiceProbeResult(
                service=service,
                address=address,
                port=0,
                is_available=False,
                response_time_ms=0.0,
                error_message=f"Unknown service: {service}",
            )

        start_time = time.time()

        try:
            if service == TransportService.SNMP:
                # SNMP uses UDP - perform lightweight probe
                result = await self._probe_udp_service(address, port, timeout)
            else:
                # TCP-based services
                result = await self._probe_tcp_service(address, port, timeout)

            elapsed_ms = (time.time() - start_time) * 1000

            return ServiceProbeResult(
                service=service,
                address=address,
                port=port,
                is_available=result,
                response_time_ms=elapsed_ms,
                error_message=None if result else "Service not responding",
            )

        except asyncio.TimeoutError:
            elapsed_ms = (time.time() - start_time) * 1000
            return ServiceProbeResult(
                service=service,
                address=address,
                port=port,
                is_available=False,
                response_time_ms=elapsed_ms,
                error_message="Connection timeout",
            )

        except Exception as exc:
            elapsed_ms = (time.time() - start_time) * 1000
            return ServiceProbeResult(
                service=service,
                address=address,
                port=port,
                is_available=False,
                response_time_ms=elapsed_ms,
                error_message=str(exc),
            )

    async def _probe_tcp_service(
        self,
        address: str,
        port: int,
        timeout: float,
    ) -> bool:
        """Probe a TCP service by attempting a connection."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(address, port),
                timeout=timeout,
            )
            # Immediately close - we just wanted to check availability
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError):
            return False

    async def _probe_udp_service(
        self,
        address: str,
        port: int,
        timeout: float,
    ) -> bool:
        """Probe a UDP service (SNMP) by attempting a datagram send."""
        try:
            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)

            try:
                # Try to send an empty datagram
                await asyncio.wait_for(
                    loop.sock_sendto(sock, b"", (address, port)),
                    timeout=timeout,
                )
                # For UDP, a successful send doesn't guarantee service availability
                # but it suggests the host is reachable
                return True
            except asyncio.TimeoutError:
                return False
            finally:
                sock.close()
        except Exception:
            return False


def get_service_for_capability(capability: TransportCapability) -> TransportService | None:
    """Map a TransportCapability to its corresponding TransportService."""
    capability_str = str(capability).upper()
    service_name = CAPABILITY_TO_SERVICE.get(capability_str)
    if service_name:
        return service_name
    return None


def get_capabilities_from_services(
    services: list[TransportService],
) -> list[TransportCapability]:
    """Get TransportCapabilities corresponding to given services."""
    from backend.app.transports.base import TransportCapability

    capabilities = []
    for service in services:
        # Map service back to capability
        for cap_name, svc in CAPABILITY_TO_SERVICE.items():
            if svc == service:
                try:
                    capabilities.append(TransportCapability(cap_name))
                except ValueError:
                    pass
                break
    return capabilities


__all__ = [
    "TransportService",
    "TRANSPORT_PORTS",
    "ServiceProbeResult",
    "HostProbeResult",
    "ServiceProber",
    "get_service_for_capability",
    "get_capabilities_from_services",
]