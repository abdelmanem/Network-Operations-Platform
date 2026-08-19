from datetime import UTC, datetime
from uuid import uuid4

import pytest
from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryJobStatus,
    DiscoveryTraceability,
    transition_job,
)


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
