"""Multi-transport discovery orchestration with fallback support.

This module provides the core orchestration logic for multi-transport network
discovery, enabling automatic fallback between management protocols (SSH,
Telnet, HTTP/HTTPS, SNMP) while maintaining accurate result classification.

The orchestrator ensures:
- Deterministic transport priority based on credential profile configuration
- Every transport attempt is recorded for audit and troubleshooting
- Host reachability is determined independently of management transport success
- Authentication failures are distinguished from transport unavailability
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from backend.app.discovery.contracts import DiscoveryFailureCode
from backend.app.discovery.probing import (
    HostProbeResult,
    ServiceProber,
    TransportService,
    get_service_for_capability,
)
from backend.app.discovery.result_states import (
    DiscoveryResultState,
    classify_transport_failure,
)
from backend.app.transports.base import TransportCapability

if TYPE_CHECKING:
    from backend.app.collectors.base import BaseCollector
    from backend.app.collectors.context import CollectorContext
    from backend.app.persistence.discovery_repositories import (
        DiscoveryTransportAttemptRepository,
    )
    from backend.app.persistence.models import (
        DiscoveryDeviceResultRecord,
    )


@dataclass(frozen=True, slots=True)
class TransportAttemptConfig:
    """Configuration for a single transport attempt in the fallback chain."""

    transport_name: str
    capability: TransportCapability
    collector: BaseCollector
    context: CollectorContext
    is_insecure: bool = False


@dataclass(frozen=True, slots=True)
class TransportAttemptResult:
    """Result of a single transport attempt."""

    transport_name: str
    attempt_order: int
    success: bool
    failure_code: DiscoveryFailureCode | None = None
    failure_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    payload: dict[str, Any] | None = None
    device_info: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class MultiTransportDiscoveryResult:
    """Complete result of multi-transport discovery with fallback."""

    address: str
    result_state: DiscoveryResultState
    selected_transport: str | None
    attempts: list[TransportAttemptResult]
    discovery_payload: dict[str, Any] | None = None
    device_info: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def was_discovered(self) -> bool:
        """Return True if device was successfully discovered."""
        return self.result_state == DiscoveryResultState.DISCOVERED

    @property
    def is_reachable(self) -> bool:
        """Return True if host was reachable."""
        return self.result_state.is_reachable

    @property
    def attempt_count(self) -> int:
        """Return the number of transport attempts made."""
        return len(self.attempts)


class MultiTransportDiscoveryOrchestrator:
    """Orchestrates multi-transport discovery with automatic fallback.

    This orchestrator manages the discovery process across multiple management
transports, implementing fallback logic when primary transports fail while
maintaining accurate result classification and audit trails.

    Key responsibilities:
    - Execute transport attempts in configured priority order
    - Record every attempt for troubleshooting and compliance
    - Determine accurate result states (unreachable, auth failed, discovered, etc.)
    - Support service probing to optimize transport ordering
    """

    def __init__(
        self,
        *,
        service_prober: ServiceProber | None = None,
        enable_service_probing: bool = False,
        allow_reorder_transports: bool = False,
        default_timeout_seconds: float = 30.0,
    ) -> None:
        self.service_prober = service_prober or ServiceProber()
        self.enable_service_probing = enable_service_probing
        self.allow_reorder_transports = allow_reorder_transports
        self.default_timeout = default_timeout_seconds

    async def discover_with_fallback(
        self,
        address: str,
        transport_configs: list[TransportAttemptConfig],
        *,
        attempts_repository: DiscoveryTransportAttemptRepository | None = None,
        device_result: DiscoveryDeviceResultRecord | None = None,
        probe_services: bool | None = None,
    ) -> MultiTransportDiscoveryResult:
        """Execute discovery with automatic transport fallback.

        Attempts each configured transport in order until one succeeds,
recording all attempts and determining the appropriate result state.

        Args:
            address: Target IP address or hostname
            transport_configs: Ordered list of transport configurations to attempt
            attempts_repository: Optional repository to persist attempt records
            device_result: Optional device result record to associate with attempts
            probe_services: Whether to probe services first (defaults to enable_service_probing)

        Returns:
            MultiTransportDiscoveryResult with complete discovery outcome
        """
        started_at = datetime.now(UTC)
        should_probe = (
            probe_services
            if probe_services is not None
            else self.enable_service_probing
        )

        # Optional service probing to inform diagnostics only (no reorder by default)
        available_services: list[TransportService] = []
        if should_probe and len(transport_configs) > 1:
            try:
                probe_result = await self._probe_services_for_host(
                    address, transport_configs
                )
                available_services = probe_result.get_available_services()
                # Only reorder transports if explicitly enabled (policy: deterministic order)
                if self.allow_reorder_transports:
                    transport_configs = self._reorder_transports_by_availability(
                        transport_configs, available_services
                    )
            except Exception:
                # Probing failure shouldn't stop discovery - continue with original order
                pass

        # Execute transport attempts in order
        attempt_results: list[TransportAttemptResult] = []
        successful_payload: dict[str, Any] | None = None
        selected_transport: str | None = None
        device_info: dict[str, Any] | None = None

        # Track overall outcome indicators
        host_is_reachable = False
        any_auth_failed = False
        any_service_available = False
        has_partial_data = False
        is_fully_discovered = False

        for attempt_order, config in enumerate(transport_configs, start=1):
            attempt_started = datetime.now(UTC)

            # Record attempt start if repository provided
            attempt_record = None
            if attempts_repository and device_result:
                try:
                    attempt_record = attempts_repository.start(
                        tenant_id=device_result.tenant_id,
                        device_result_id=device_result.id,
                        transport=config.transport_name,
                        attempt_order=attempt_order,
                        correlation_id=device_result.correlation_id,
                    )
                except Exception:
                    # Attempt recording failure shouldn't stop discovery
                    pass

            # Execute the transport attempt
            attempt_result = await self._execute_transport_attempt(
                config=config,
                attempt_order=attempt_order,
                attempt_started=attempt_started,
            )

            attempt_results.append(attempt_result)

            # Update outcome indicators based on attempt result
            if attempt_result.success:
                host_is_reachable = True
                any_service_available = True
                selected_transport = config.transport_name
                successful_payload = attempt_result.payload
                device_info = attempt_result.device_info
                is_fully_discovered = True

                # Finish attempt record as success
                if attempt_record and attempts_repository:
                    try:
                        attempts_repository.finish(
                            attempt_record,
                            result="success",
                        )
                    except Exception:
                        pass

                # Stop attempting other transports - we have success
                break

            else:
                # Analyze failure for outcome classification
                is_reachable, auth_failed, service_avail = classify_transport_failure(
                    attempt_result.failure_code.value
                    if attempt_result.failure_code
                    else None
                )

                if is_reachable:
                    host_is_reachable = True
                if auth_failed:
                    any_auth_failed = True
                if service_avail:
                    any_service_available = True

                # Determine failure code for attempt record
                failure_code_str = None
                if attempt_result.failure_code:
                    failure_code_str = attempt_result.failure_code.value

                # Finish attempt record as failed
                if attempt_record and attempts_repository:
                    try:
                        attempts_repository.finish(
                            attempt_record,
                            result="failed",
                            failure_code=failure_code_str,
                        )
                    except Exception:
                        pass

        # Determine final result state
        completed_at = datetime.now(UTC)

        # Use the classification function to determine result state
        result_state = DiscoveryResultState.from_failure_and_success(
            is_reachable=host_is_reachable,
            has_management_service=any_service_available,
            auth_failed=any_auth_failed,
            has_partial_data=has_partial_data,
            is_fully_discovered=is_fully_discovered,
        )

        return MultiTransportDiscoveryResult(
            address=address,
            result_state=result_state,
            selected_transport=selected_transport,
            attempts=attempt_results,
            discovery_payload=successful_payload,
            device_info=device_info,
            started_at=started_at,
            completed_at=completed_at,
        )

    async def _probe_services_for_host(
        self,
        address: str,
        transport_configs: list[TransportAttemptConfig],
    ) -> HostProbeResult:
        """Probe which services are available for a host."""
        # Determine which services to probe based on transport configs
        services_to_probe: list[TransportService] = []
        for config in transport_configs:
            service = get_service_for_capability(config.capability)
            if service and service not in services_to_probe:
                services_to_probe.append(service)

        return await self.service_prober.probe_host(address, services_to_probe)

    def _reorder_transports_by_availability(
        self,
        transport_configs: list[TransportAttemptConfig],
        available_services: list[TransportService],
    ) -> list[TransportAttemptConfig]:
        """Reorder transport configs to prioritize available services.

        Maintains relative order within available and unavailable groups.
        """
        available_configs: list[TransportAttemptConfig] = []
        unavailable_configs: list[TransportAttemptConfig] = []

        for config in transport_configs:
            service = get_service_for_capability(config.capability)
            if service and service in available_services:
                available_configs.append(config)
            else:
                unavailable_configs.append(config)

        return available_configs + unavailable_configs

    async def _execute_transport_attempt(
        self,
        config: TransportAttemptConfig,
        attempt_order: int,
        attempt_started: datetime,
    ) -> TransportAttemptResult:
        """Execute a single transport attempt using the configured collector."""
        try:
            # Perform health check
            await config.collector.health_check(config.context)

            # Attempt to collect data
            payload = await config.collector.collect(
                config.context,
                discovered_targets=(),
            )

            # Determine if we got useful data
            if payload and isinstance(payload, dict):
                # Extract device info if present
                device_info: dict[str, Any] | None = None
                if "device_info" in payload and isinstance(payload["device_info"], dict):
                    device_info = dict(payload["device_info"])
                elif "facts" in payload and isinstance(payload["facts"], dict):
                    device_info = dict(payload["facts"])
                else:
                    extracted: dict[str, Any] = {}
                    for key in ["hostname", "platform", "vendor", "model", "serial_number"]:
                        if key in payload and payload[key] is not None:
                            extracted[key] = payload[key]
                    if extracted:
                        device_info = extracted

                # Check for device identification in payload
                has_device_info = any(
                    key in payload
                    for key in ["device_info", "facts", "inventory", "hostname", "platform"]
                )

                if has_device_info or payload.get("success"):
                    completed_at = datetime.now(UTC)
                    duration_ms = int(
                        (completed_at - attempt_started).total_seconds() * 1000
                    )

                    return TransportAttemptResult(
                        transport_name=config.transport_name,
                        attempt_order=attempt_order,
                        success=True,
                        started_at=attempt_started,
                        completed_at=completed_at,
                        duration_ms=duration_ms,
                        payload=dict(payload),
                        device_info=device_info,
                    )

            # If we get here, the attempt didn't yield useful data
            completed_at = datetime.now(UTC)
            duration_ms = int((completed_at - attempt_started).total_seconds() * 1000)

            return TransportAttemptResult(
                transport_name=config.transport_name,
                attempt_order=attempt_order,
                success=False,
                failure_code=DiscoveryFailureCode.DISCOVERY_FAILED,
                failure_message="Collector did not return device identification data",
                started_at=attempt_started,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            completed_at = datetime.now(UTC)
            duration_ms = int((completed_at - attempt_started).total_seconds() * 1000)

            # Classify the exception
            failure_code = self._classify_exception(exc)
            failure_message = str(exc)[:500]  # Limit message length

            return TransportAttemptResult(
                transport_name=config.transport_name,
                attempt_order=attempt_order,
                success=False,
                failure_code=failure_code,
                failure_message=failure_message,
                started_at=attempt_started,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )

    def _classify_exception(self, exc: Exception) -> DiscoveryFailureCode:
        """Classify an exception into a DiscoveryFailureCode."""
        message = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        # Authentication-related errors
        if any(
            term in message
            for term in ["authentication", "unauthorized", "credential", "login", "auth"]
        ):
            return DiscoveryFailureCode.AUTHENTICATION_FAILED

        # Connection refused
        if "refused" in message or exc_type == "connectionrefusederror":
            return DiscoveryFailureCode.CONNECTION_REFUSED

        # Timeout errors
        if any(term in message for term in ["timeout", "timed out"]) or exc_type in [
            "timeouterror",
            "asyncio.timeouterror",
        ]:
            return DiscoveryFailureCode.CONNECTION_TIMEOUT

        # Connection failures
        if any(term in message for term in ["connection", "network", "unreachable"]):
            return DiscoveryFailureCode.CONNECTION_FAILED

        # Transport unavailable
        if "transport" in message:
            return DiscoveryFailureCode.TRANSPORT_UNAVAILABLE

        # Default to generic discovery failure
        return DiscoveryFailureCode.DISCOVERY_FAILED


__all__ = [
    "MultiTransportDiscoveryOrchestrator",
    "MultiTransportDiscoveryResult",
    "TransportAttemptConfig",
    "TransportAttemptResult",
]