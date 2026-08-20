from datetime import UTC, datetime
from uuid import uuid4

import pytest
from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryJobStatus,
    DiscoveryScopeType,
    DiscoveryTraceability,
    DiscoveryTransportPolicy,
    transition_job,
    validate_scope,
)
from backend.app.discovery.scopes import DiscoveryScope, DiscoveryScopeError
from backend.app.transports.base import TransportCapability


def test_discovery_job_state_machine_allows_only_valid_transitions() -> None:
    assert (
        transition_job(DiscoveryJobStatus.QUEUED, DiscoveryJobStatus.RUNNING)
        == DiscoveryJobStatus.RUNNING
    )
    assert (
        transition_job(DiscoveryJobStatus.RUNNING, DiscoveryJobStatus.SUCCEEDED)
        == DiscoveryJobStatus.SUCCEEDED
    )

    with pytest.raises(ValueError, match="Invalid discovery job transition"):
        transition_job(DiscoveryJobStatus.QUEUED, DiscoveryJobStatus.SUCCEEDED)

    with pytest.raises(ValueError, match="Invalid discovery job transition"):
        transition_job(DiscoveryJobStatus.SUCCEEDED, DiscoveryJobStatus.RUNNING)


def test_terminal_discovery_job_states_are_terminal() -> None:
    assert DiscoveryJobStatus.QUEUED.is_terminal is False
    assert DiscoveryJobStatus.RUNNING.is_terminal is False
    assert DiscoveryJobStatus.SUCCEEDED.is_terminal is True
    assert DiscoveryJobStatus.FAILED.is_terminal is True
    assert DiscoveryJobStatus.TIMED_OUT.is_terminal is True
    assert DiscoveryJobStatus.CANCELLED.is_terminal is True


def test_transport_policy_is_explicit_and_does_not_implicitly_try_telnet() -> None:
    policy = DiscoveryTransportPolicy(
        preferred=TransportCapability.SNMP,
        fallbacks=(TransportCapability.SSH,),
    )

    assert policy.ordered() == (
        TransportCapability.SNMP,
        TransportCapability.SSH,
    )

    with pytest.raises(ValueError, match="Telnet"):
        DiscoveryTransportPolicy(
            preferred=TransportCapability.SSH,
            fallbacks=(TransportCapability.TELNET,),
        ).ordered()


def test_scope_validation_supports_single_device_range_and_cidr() -> None:
    validate_scope(DiscoveryScopeType.SINGLE_DEVICE, address="10.0.0.1")
    validate_scope(
        DiscoveryScopeType.IP_RANGE,
        address="10.0.0.1",
        scope_end="10.0.0.10",
    )
    validate_scope(
        DiscoveryScopeType.CIDR_NETWORK,
        scope_cidr="10.0.0.0/24",
    )

    with pytest.raises(ValueError):
        validate_scope(
            DiscoveryScopeType.IP_RANGE,
            address="10.0.0.10",
            scope_end="10.0.0.1",
        )


def test_scope_expansion_is_bounded_for_single_range_and_cidr() -> None:
    assert DiscoveryScope(
        DiscoveryScopeType.SINGLE_DEVICE, address="10.0.0.1"
    ).expand() == ("10.0.0.1",)
    assert DiscoveryScope(
        DiscoveryScopeType.IP_RANGE,
        address="10.0.0.1",
        scope_end="10.0.0.3",
    ).expand() == ("10.0.0.1", "10.0.0.2", "10.0.0.3")
    assert DiscoveryScope(
        DiscoveryScopeType.CIDR_NETWORK, scope_cidr="192.0.2.0/30"
    ).expand() == ("192.0.2.1", "192.0.2.2")

    with pytest.raises(DiscoveryScopeError, match="target limit"):
        DiscoveryScope(
            DiscoveryScopeType.CIDR_NETWORK, scope_cidr="10.0.0.0/24"
        ).expand(max_targets=10)


def test_evidence_is_traceable_and_hashable() -> None:
    traceability = DiscoveryTraceability(
        tenant_id="tenant-a",
        target_id=uuid4(),
        job_id=uuid4(),
        discovery_run_id=uuid4(),
    )
    evidence = DiscoveryEvidence(
        traceability=traceability,
        collector_name="cisco-iosxe-discovery",
        platform="cisco-iosxe",
        transport="ssh",
        evidence_type="command_output",
        command_or_probe="show version",
        payload={"hostname": "core-01", "version": "17.12"},
        captured_at=datetime.now(UTC),
        sequence=0,
    )

    assert evidence.verify_hash() is True
    assert evidence.content_hash == evidence.compute_hash()
    assert evidence.traceability.tenant_id == "tenant-a"
    assert evidence.traceability.job_id is not None


def test_evidence_requires_timezone_aware_timestamp() -> None:
    traceability = DiscoveryTraceability(
        tenant_id="tenant-a",
        target_id=uuid4(),
        job_id=uuid4(),
        discovery_run_id=uuid4(),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        DiscoveryEvidence(
            traceability=traceability,
            collector_name="collector",
            platform="cisco-iosxe",
            transport="ssh",
            evidence_type="command_output",
            command_or_probe="show version",
            payload={},
            captured_at=datetime(2026, 8, 19),
            sequence=0,
        )
