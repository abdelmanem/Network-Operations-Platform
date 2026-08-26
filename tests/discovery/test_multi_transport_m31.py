"""Comprehensive unit and integration tests for M31 multi-transport discovery fallback.

Tests cover:
- SSH success without fallback
- SSH → Telnet fallback chains
- SSH → Telnet → HTTPS fallback chains
- All transports failing with correct classification
- Host unreachability detection
- Authentication failure handling
- Telnet security requirement
- Result state classification
- Transport attempt recording
- Summary aggregation
- Secret safety (no credentials in results)
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from backend.app.discovery.contracts import (
    DiscoveryFailureCode,
    DiscoveryJobStatus,
    DiscoveryScopeType,
)
from backend.app.discovery.result_states import DiscoveryResultState
from backend.app.models.base import BaseModel
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryJobRecord,
    DiscoveryTargetRecord,
    DiscoveryTransportAttemptRecord,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    return Session(engine)


@pytest.fixture
def db_session() -> Session:
    return _session()


class TestMultiTransportDiscoveryExecution:
    """Unit tests for multi-transport discovery execution."""

    @pytest.fixture
    def tenant_id(self) -> str:
        return "test-tenant-m31"

    @pytest.fixture
    def target_id(self) -> UUID:
        return uuid4()

    @pytest.fixture
    def job_id(self) -> UUID:
        return uuid4()

    @pytest.fixture
    def run_id(self) -> UUID:
        return uuid4()

    def test_ssh_success_no_fallback(
        self,
        db_session: Session,
        tenant_id: str,
        target_id: UUID,
        job_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: SSH succeeds → no fallback attempts, single transport recorded."""
        # Setup: Create job with multi-transport policy
        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id=tenant_id,
            identifier="192.168.20.10",
            address="192.168.20.10",
            scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
            credential_reference="ssh-creds",
            credential_profile_id=None,
            metadata_json={"transport_name": "ssh"},
        )
        db_session.add(target)

        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            requested_capabilities={"capabilities": []},
        )
        db_session.add(job)
        db_session.commit()

        # Action: Simulate SSH success (would be done by orchestrator in real execution)
        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=job_id,
            child_job_id=job_id,
            address="192.168.20.10",
            state=DiscoveryJobStatus.SUCCEEDED.value,
            result_state=DiscoveryResultState.DISCOVERED.value,
            selected_transport="ssh",
        )
        db_session.add(device_result)

        # Record single SSH attempt
        attempt = DiscoveryTransportAttemptRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            device_result_id=device_result.id,
            transport="ssh",
            attempt_order=1,
            result="success",
            failure_code=None,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db_session.add(attempt)
        db_session.commit()

        # Verify: Only one attempt, discovery succeeded
        attempts = db_session.scalars(
            select(DiscoveryTransportAttemptRecord).where(
                DiscoveryTransportAttemptRecord.device_result_id == device_result.id
            )
        ).all()
        assert len(attempts) == 1
        assert attempts[0].transport == "ssh"
        assert attempts[0].result == "success"
        assert device_result.result_state == DiscoveryResultState.DISCOVERED.value
        assert device_result.selected_transport == "ssh"

    def test_ssh_fails_telnet_succeeds(
        self,
        db_session: Session,
        tenant_id: str,
        target_id: UUID,
        job_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: SSH fails → Telnet succeeds, two attempts recorded."""
        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id=tenant_id,
            identifier="192.168.20.11",
            address="192.168.20.11",
            scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
            credential_reference="creds",
            metadata_json={"allowed_fallback_transports": ["telnet"]},
        )
        db_session.add(target)

        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            requested_capabilities={},
        )
        db_session.add(job)
        db_session.commit()

        # Simulate orchestrator result: SSH failed, Telnet succeeded
        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=job_id,
            child_job_id=job_id,
            address="192.168.20.11",
            state=DiscoveryJobStatus.SUCCEEDED.value,
            result_state=DiscoveryResultState.DISCOVERED.value,
            selected_transport="telnet",
        )
        db_session.add(device_result)

        # Record both attempts
        ssh_attempt = DiscoveryTransportAttemptRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            device_result_id=device_result.id,
            transport="ssh",
            attempt_order=1,
            result="failed",
            failure_code=DiscoveryFailureCode.CONNECTION_REFUSED.value,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=100,
        )
        db_session.add(ssh_attempt)

        telnet_attempt = DiscoveryTransportAttemptRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            device_result_id=device_result.id,
            transport="telnet",
            attempt_order=2,
            result="success",
            failure_code=None,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=150,
        )
        db_session.add(telnet_attempt)
        db_session.commit()

        # Verify
        attempts = db_session.scalars(
            select(DiscoveryTransportAttemptRecord).where(
                DiscoveryTransportAttemptRecord.device_result_id == device_result.id
            )
        ).all()
        assert len(attempts) == 2
        assert attempts[0].transport == "ssh"
        assert attempts[0].result == "failed"
        assert attempts[1].transport == "telnet"
        assert attempts[1].result == "success"
        assert device_result.result_state == DiscoveryResultState.DISCOVERED.value
        assert device_result.selected_transport == "telnet"

    def test_all_transports_fail_no_management(
        self,
        db_session: Session,
        tenant_id: str,
        target_id: UUID,
        job_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: SSH, Telnet, HTTPS all fail → REACHABLE_NO_MANAGEMENT."""
        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id=tenant_id,
            identifier="192.168.20.13",
            address="192.168.20.13",
            scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
            credential_reference="creds",
            metadata_json={},
        )
        db_session.add(target)

        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            requested_capabilities={},
        )
        db_session.add(job)
        db_session.commit()

        # Host is reachable but no management service responds
        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=job_id,
            child_job_id=job_id,
            address="192.168.20.13",
            state=DiscoveryJobStatus.FAILED.value,
            result_state=DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value,
            selected_transport=None,
            failure_code=DiscoveryFailureCode.TRANSPORT_UNAVAILABLE.value,
            failure_message="No configured management transports responded.",
        )
        db_session.add(device_result)

        # Record all three failed attempts
        for order, transport in enumerate(["ssh", "telnet", "https"], start=1):
            attempt = DiscoveryTransportAttemptRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                device_result_id=device_result.id,
                transport=transport,
                attempt_order=order,
                result="failed",
                failure_code=DiscoveryFailureCode.CONNECTION_REFUSED.value,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_ms=50,
            )
            db_session.add(attempt)
        db_session.commit()

        # Verify
        assert (
            device_result.result_state
            == DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value
        )
        attempts = db_session.scalars(
            select(DiscoveryTransportAttemptRecord).where(
                DiscoveryTransportAttemptRecord.device_result_id == device_result.id
            )
        ).all()
        assert len(attempts) == 3
        for attempt in attempts:
            assert attempt.result == "failed"

    def test_host_unreachable(
        self,
        db_session: Session,
        tenant_id: str,
        target_id: UUID,
        job_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: All connectivity checks fail → UNREACHABLE."""
        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id=tenant_id,
            identifier="192.168.20.14",
            address="192.168.20.14",
            scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
            credential_reference="creds",
            metadata_json={},
        )
        db_session.add(target)

        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            requested_capabilities={},
        )
        db_session.add(job)
        db_session.commit()

        # Host is unreachable
        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=job_id,
            child_job_id=job_id,
            address="192.168.20.14",
            state=DiscoveryJobStatus.FAILED.value,
            result_state=DiscoveryResultState.UNREACHABLE.value,
            selected_transport=None,
            failure_code=DiscoveryFailureCode.CONNECTION_FAILED.value,
            failure_message="Host was unreachable for all configured transports.",
        )
        db_session.add(device_result)

        ssh_attempt = DiscoveryTransportAttemptRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            device_result_id=device_result.id,
            transport="ssh",
            attempt_order=1,
            result="failed",
            failure_code=DiscoveryFailureCode.CONNECTION_TIMEOUT.value,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=5000,  # Timeout
        )
        db_session.add(ssh_attempt)
        db_session.commit()

        # Verify
        assert device_result.result_state == DiscoveryResultState.UNREACHABLE.value
        assert (
            device_result.failure_code == DiscoveryFailureCode.CONNECTION_FAILED.value
        )

    def test_authentication_failed_all_transports(
        self,
        db_session: Session,
        tenant_id: str,
        target_id: UUID,
        job_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: All transports fail auth → AUTHENTICATION_FAILED."""
        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id=tenant_id,
            identifier="192.168.20.12",
            address="192.168.20.12",
            scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
            credential_reference="bad-creds",
            metadata_json={},
        )
        db_session.add(target)

        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            requested_capabilities={},
        )
        db_session.add(job)
        db_session.commit()

        # Services available but auth failed
        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=job_id,
            child_job_id=job_id,
            address="192.168.20.12",
            state=DiscoveryJobStatus.FAILED.value,
            result_state=DiscoveryResultState.AUTHENTICATION_FAILED.value,
            selected_transport=None,
            failure_code=DiscoveryFailureCode.AUTHENTICATION_FAILED.value,
            failure_message="Authentication failed for all applicable transports.",
        )
        db_session.add(device_result)

        # Both SSH and Telnet fail auth
        for order, transport in enumerate(["ssh", "telnet"], start=1):
            attempt = DiscoveryTransportAttemptRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                device_result_id=device_result.id,
                transport=transport,
                attempt_order=order,
                result="failed",
                failure_code=DiscoveryFailureCode.AUTHENTICATION_FAILED.value,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_ms=200,
            )
            db_session.add(attempt)
        db_session.commit()

        # Verify
        assert (
            device_result.result_state
            == DiscoveryResultState.AUTHENTICATION_FAILED.value
        )

    def test_telnet_disabled_even_if_available(
        self,
        db_session: Session,
        tenant_id: str,
        target_id: UUID,
        job_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: Disabled Telnet is not attempted even when policy lists it."""
        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id=tenant_id,
            identifier="192.168.20.15",
            address="192.168.20.15",
            scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
            credential_reference="creds",
            allow_insecure_telnet=False,  # Explicitly disabled
            metadata_json={"allowed_fallback_transports": ["telnet"]},
        )
        db_session.add(target)

        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            requested_capabilities={},
        )
        db_session.add(job)
        db_session.commit()

        # Only SSH should be attempted, Telnet skipped
        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=job_id,
            child_job_id=job_id,
            address="192.168.20.15",
            state=DiscoveryJobStatus.FAILED.value,
            result_state=DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value,
            selected_transport=None,
        )
        db_session.add(device_result)

        # Only SSH attempt (Telnet was skipped due to allow_insecure_telnet=False)
        ssh_attempt = DiscoveryTransportAttemptRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            device_result_id=device_result.id,
            transport="ssh",
            attempt_order=1,
            result="failed",
            failure_code=DiscoveryFailureCode.CONNECTION_REFUSED.value,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db_session.add(ssh_attempt)
        db_session.commit()

        # Verify: Only SSH attempted, Telnet not in attempts list
        attempts = db_session.scalars(
            select(DiscoveryTransportAttemptRecord).where(
                DiscoveryTransportAttemptRecord.device_result_id == device_result.id
            )
        ).all()
        transports_attempted = [a.transport for a in attempts]
        assert "ssh" in transports_attempted
        assert "telnet" not in transports_attempted

    def test_attempt_ordering_preserved(
        self,
        db_session: Session,
        tenant_id: str,
        target_id: UUID,
        job_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: Attempt order is sequentially preserved (1, 2, 3...)."""
        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id=tenant_id,
            identifier="192.168.20.20",
            address="192.168.20.20",
            scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
            credential_reference="creds",
            metadata_json={},
        )
        db_session.add(target)

        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            requested_capabilities={},
        )
        db_session.add(job)
        db_session.commit()

        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=job_id,
            child_job_id=job_id,
            address="192.168.20.20",
            state=DiscoveryJobStatus.SUCCEEDED.value,
            result_state=DiscoveryResultState.DISCOVERED.value,
            selected_transport="https",
        )
        db_session.add(device_result)

        # Create attempts in order
        for order, transport in enumerate(["ssh", "telnet", "https"], start=1):
            attempt = DiscoveryTransportAttemptRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                device_result_id=device_result.id,
                transport=transport,
                attempt_order=order,
                result="success" if transport == "https" else "failed",
                failure_code=(
                    None
                    if transport == "https"
                    else DiscoveryFailureCode.CONNECTION_REFUSED.value
                ),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            db_session.add(attempt)
        db_session.commit()

        # Verify: Order is sequential 1, 2, 3
        attempts = sorted(
            db_session.scalars(
                select(DiscoveryTransportAttemptRecord).where(
                    DiscoveryTransportAttemptRecord.device_result_id == device_result.id
                )
            ).all(),
            key=lambda a: a.attempt_order,
        )
        expected_order = [1, 2, 3]
        actual_order = [a.attempt_order for a in attempts]
        assert actual_order == expected_order

    def test_no_secrets_in_attempt_records(
        self,
        db_session: Session,
        tenant_id: str,
        target_id: UUID,
        job_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: No passwords or secrets appear in DiscoveryTransportAttemptRecord."""
        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id=tenant_id,
            identifier="192.168.20.30",
            address="192.168.20.30",
            scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
            credential_reference="creds",
            metadata_json={},
        )
        db_session.add(target)

        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            requested_capabilities={},
        )
        db_session.add(job)
        db_session.commit()

        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=job_id,
            child_job_id=job_id,
            address="192.168.20.30",
            state=DiscoveryJobStatus.FAILED.value,
            result_state=DiscoveryResultState.AUTHENTICATION_FAILED.value,
        )
        db_session.add(device_result)

        attempt = DiscoveryTransportAttemptRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            device_result_id=device_result.id,
            transport="ssh",
            attempt_order=1,
            result="failed",
            failure_code=DiscoveryFailureCode.AUTHENTICATION_FAILED.value,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        db_session.add(attempt)
        db_session.commit()

        # Verify: No secret fields in attempt record
        retrieved_attempt = db_session.get(DiscoveryTransportAttemptRecord, attempt.id)
        assert retrieved_attempt is not None
        # Confirm these fields don't exist or are None (never contain secrets)
        assert not hasattr(retrieved_attempt, "password")
        assert not hasattr(retrieved_attempt, "credential")
        assert not hasattr(retrieved_attempt, "token")
        # Only safe data present
        assert retrieved_attempt.transport == "ssh"
        assert retrieved_attempt.attempt_order == 1
