"""Discovery result classification states.

This module defines the comprehensive result classification system for network
discovery operations. It distinguishes between different types of discovery
outcomes to provide accurate reporting and troubleshooting capabilities.

The classification system ensures:
- Host reachability is determined independently of management transport availability
- Authentication failures are distinguished from network unreachability
- Partial discoveries are tracked separately from complete failures
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.discovery.contracts import DiscoveryFailureCode


class DiscoveryResultState(StrEnum):
    """Comprehensive discovery result classification states.

    These states provide granular visibility into discovery outcomes,
    enabling accurate reporting and troubleshooting in heterogeneous
    network environments.

    States are ordered from least to most successful:
    UNREACHABLE < REACHABLE_NO_MANAGEMENT < AUTHENTICATION_FAILED < PARTIAL_DISCOVERY < DISCOVERED
    """

    # Host could not be reached via any configured connectivity check
    UNREACHABLE = "unreachable"

    # Host is reachable but none of the configured management transports succeeded
    REACHABLE_NO_MANAGEMENT = "reachable_no_management"

    # Management service was reached but authentication failed for all applicable transports
    AUTHENTICATION_FAILED = "authentication_failed"

    # Device was identified and some data collected but full discovery did not complete
    PARTIAL_DISCOVERY = "partial_discovery"

    # Full successful discovery with complete inventory collection
    DISCOVERED = "discovered"

    @property
    def is_reachable(self) -> bool:
        """Return True if the host was reachable at the IP layer."""
        return self != DiscoveryResultState.UNREACHABLE

    @property
    def is_discovered(self) -> bool:
        """Return True if full discovery was successful."""
        return self == DiscoveryResultState.DISCOVERED

    @property
    def is_terminal(self) -> bool:
        """Return True if this represents a final discovery state."""
        return True  # All states are terminal; discovery is complete

    @classmethod
    def from_failure_and_success(
        cls,
        is_reachable: bool,
        has_management_service: bool,
        auth_failed: bool,
        has_partial_data: bool,
        is_fully_discovered: bool,
    ) -> DiscoveryResultState:
        """Determine the appropriate result state from outcome indicators.

        Args:
            is_reachable: Whether the host responded at the IP layer
            has_management_service: Whether any management service was available
            auth_failed: Whether authentication failed for available services
            has_partial_data: Whether partial discovery data was collected
            is_fully_discovered: Whether full discovery succeeded

        Returns:
            The appropriate DiscoveryResultState classification
        """
        if is_fully_discovered:
            return cls.DISCOVERED

        if has_partial_data:
            return cls.PARTIAL_DISCOVERY

        if auth_failed:
            return cls.AUTHENTICATION_FAILED

        if not is_reachable:
            return cls.UNREACHABLE

        if not has_management_service:
            return cls.REACHABLE_NO_MANAGEMENT

        # Fallback - should not reach here if inputs are consistent
        return cls.REACHABLE_NO_MANAGEMENT


def classify_transport_failure(
    failure_code: DiscoveryFailureCode | str | None,
) -> tuple[bool, bool, bool]:
    """Classify a transport failure into reachability, auth, and service indicators.

    Args:
        failure_code: The discovery failure code from a transport attempt

    Returns:
        Tuple of (is_reachable, auth_failed, service_available) booleans
    """
    from backend.app.discovery.contracts import DiscoveryFailureCode

    if failure_code is None:
        # Success case - all good
        return True, False, True

    if isinstance(failure_code, str):
        try:
            failure_code = DiscoveryFailureCode(failure_code)
        except ValueError:
            # Unknown failure code - assume not reachable
            return False, False, False

    # Authentication failures indicate reachability but auth failure
    if failure_code == DiscoveryFailureCode.AUTHENTICATION_FAILED:
        return True, True, True

    # Credential resolution failures are auth-related
    if failure_code == DiscoveryFailureCode.CREDENTIAL_RESOLUTION_FAILED:
        return True, True, False

    # Unsupported credential for this transport - host up, auth not attempted
    if failure_code == DiscoveryFailureCode.UNSUPPORTED_CREDENTIAL:
        return True, False, True

    # Transport disabled by policy (e.g. Telnet not allowed) - host up, service not tried
    if failure_code == DiscoveryFailureCode.TRANSPORT_DISABLED:
        return True, False, False

    # Connection refused means reachable but service not available
    if failure_code == DiscoveryFailureCode.CONNECTION_REFUSED:
        return True, False, False

    # Connection timeouts might be network or host
    if failure_code in (
        DiscoveryFailureCode.HOST_UNREACHABLE,
        DiscoveryFailureCode.CONNECTION_TIMEOUT,
        DiscoveryFailureCode.TIMEOUT,
        DiscoveryFailureCode.DISCOVERY_TIMEOUT,
    ):
        # Assume not reachable for timeout cases
        return False, False, False

    # Transport unavailable means host might be up but service not
    if failure_code == DiscoveryFailureCode.TRANSPORT_UNAVAILABLE:
        return True, False, False

    # Connection failed - could be various reasons
    if failure_code == DiscoveryFailureCode.CONNECTION_FAILED:
        return False, False, False

    # Default - assume not reachable for unknown failures
    return False, False, False


__all__ = [
    "DiscoveryResultState",
    "classify_transport_failure",
]