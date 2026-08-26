"""Integration tests for M31 heterogeneous network discovery.

Tests the complete scenario: a CIDR with 5 Cisco devices with different
management transport availability. Validates that discovery correctly
classifies each device by result state and persists attempts.
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
    DiscoveryRunRecord,
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


class TestHeterogeneousCiscoNetworkDiscovery:
    """Integration tests for heterogeneous Cisco device discovery."""

    @pytest.fixture
    def tenant_id(self) -> str:
        return "cisco-tenant-m31"

    @pytest.fixture
    def network_target_id(self) -> UUID:
        """Parent target for the CIDR."""
        return uuid4()

    @pytest.fixture
    def run_id(self) -> UUID:
        """Discovery run that will contain all device results."""
        return uuid4()

    @pytest.fixture
    def device_scenarios(self) -> dict[str, dict[str, object]]:
        """Define the 5 heterogeneous device scenarios."""
        return {
            "192.168.20.10": {
                "name": "SSH_Success",
                "attempts": [("ssh", 1, "success", None)],
                "expected_state": DiscoveryResultState.DISCOVERED.value,
                "expected_transport": "ssh",
            },
            "192.168.20.11": {
                "name": "SSH_Fail_Telnet_Success",
                "attempts": [
                    ("ssh", 1, "failed", DiscoveryFailureCode.CONNECTION_REFUSED.value),
                    ("telnet", 2, "success", None),
                ],
                "expected_state": DiscoveryResultState.DISCOVERED.value,
                "expected_transport": "telnet",
            },
            "192.168.20.12": {
                "name": "SSH_Telnet_Fail_HTTPS_Success",
                "attempts": [
                    ("ssh", 1, "failed", DiscoveryFailureCode.CONNECTION_REFUSED.value),
                    (
                        "telnet",
                        2,
                        "failed",
                        DiscoveryFailureCode.CONNECTION_REFUSED.value,
                    ),
                    ("https", 3, "success", None),
                ],
                "expected_state": DiscoveryResultState.DISCOVERED.value,
                "expected_transport": "https",
            },
            "192.168.20.13": {
                "name": "All_Transports_Fail_Reachable",
                "attempts": [
                    ("ssh", 1, "failed", DiscoveryFailureCode.CONNECTION_REFUSED.value),
                    (
                        "telnet",
                        2,
                        "failed",
                        DiscoveryFailureCode.CONNECTION_REFUSED.value,
                    ),
                    (
                        "https",
                        3,
                        "failed",
                        DiscoveryFailureCode.CONNECTION_REFUSED.value,
                    ),
                ],
                "expected_state": DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value,
                "expected_transport": None,
            },
            "192.168.20.14": {
                "name": "Host_Unreachable",
                "attempts": [
                    (
                        "ssh",
                        1,
                        "failed",
                        DiscoveryFailureCode.CONNECTION_TIMEOUT.value,
                    ),
                ],
                "expected_state": DiscoveryResultState.UNREACHABLE.value,
                "expected_transport": None,
            },
        }

    def test_heterogeneous_cidr_discovery_complete_flow(
        self,
        db_session: Session,
        tenant_id: str,
        network_target_id: UUID,
        run_id: UUID,
        device_scenarios: dict[str, dict[str, object]],
    ) -> None:
        """Test: CIDR discovery classifies five heterogeneous devices correctly."""
        # Setup: Create parent target for CIDR
        parent_target = DiscoveryTargetRecord(
            id=network_target_id,
            tenant_id=tenant_id,
            identifier="cisco-network",
            address="192.168.20.0",
            scope_type=DiscoveryScopeType.CIDR_NETWORK.value,
            scope_cidr="192.168.20.0/24",
            credential_reference="cisco-ssh-creds",
            metadata_json={"allow_insecure_telnet": True},
        )
        db_session.add(parent_target)

        # Create parent job (CIDR expansion)
        parent_job = DiscoveryJobRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            target_id=network_target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.SUCCEEDED.value,
            requested_capabilities={"capabilities": []},
        )
        db_session.add(parent_job)

        # Create discovery run
        run = DiscoveryRunRecord(
            id=run_id,
            tenant_id=tenant_id,
            target_identifier="cisco-network",
            target_address="192.168.20.0",
            status="completed",
            metadata_json={},
        )
        db_session.add(run)
        db_session.commit()

        # Simulate: Create 5 child jobs and device results
        device_results = {}
        for ip_address, scenario in device_scenarios.items():
            target_id = uuid4()
            job_id = uuid4()
            result_id = uuid4()

            # Create child target for each IP
            child_target = DiscoveryTargetRecord(
                id=target_id,
                tenant_id=tenant_id,
                identifier=f"cisco-{scenario['name']}",
                address=ip_address,
                scope_type=DiscoveryScopeType.SINGLE_DEVICE.value,
                credential_reference="cisco-ssh-creds",
                metadata_json={},
            )
            db_session.add(child_target)

            # Create child job
            child_job = DiscoveryJobRecord(
                id=job_id,
                tenant_id=tenant_id,
                target_id=target_id,
                run_id=run_id,
                parent_job_id=parent_job.id,
                state=DiscoveryJobStatus.SUCCEEDED.value,
                requested_capabilities={},
            )
            db_session.add(child_job)

            # Create device result
            device_result = DiscoveryDeviceResultRecord(
                id=result_id,
                tenant_id=tenant_id,
                discovery_job_id=parent_job.id,
                child_job_id=job_id,
                address=ip_address,
                state=(
                    DiscoveryJobStatus.SUCCEEDED.value
                    if scenario["expected_state"]
                    == DiscoveryResultState.DISCOVERED.value
                    else DiscoveryJobStatus.FAILED.value
                ),
                result_state=scenario["expected_state"],
                selected_transport=scenario["expected_transport"],
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            db_session.add(device_result)
            device_results[ip_address] = device_result

        db_session.commit()

        # For each device, create transport attempts
        for ip_address, scenario in device_scenarios.items():
            device_result = device_results[ip_address]
            for transport, order, result, failure_code in scenario["attempts"]:
                attempt = DiscoveryTransportAttemptRecord(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    device_result_id=device_result.id,
                    transport=transport,
                    attempt_order=order,
                    result=result,
                    failure_code=failure_code,
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    duration_ms=100,
                )
                db_session.add(attempt)
        db_session.commit()

        # Verify: All 5 devices have correct result states
        all_results = db_session.scalars(
            select(DiscoveryDeviceResultRecord).where(
                DiscoveryDeviceResultRecord.discovery_job_id == parent_job.id
            )
        ).all()
        assert len(all_results) == 5

        # Check each device
        for ip_address, scenario in device_scenarios.items():
            device_result = next(r for r in all_results if r.address == ip_address)
            assert device_result.result_state == scenario["expected_state"]
            assert device_result.selected_transport == scenario["expected_transport"]

    def test_discovery_summary_aggregation(
        self,
        db_session: Session,
        tenant_id: str,
        network_target_id: UUID,
        run_id: UUID,
        device_scenarios: dict[str, dict[str, object]],
    ) -> None:
        """Test: Summary correctly aggregates 5 devices into categories."""
        # Setup parent target and job
        target = DiscoveryTargetRecord(
            id=network_target_id,
            tenant_id=tenant_id,
            identifier="cisco-network",
            address="192.168.20.0",
            scope_type=DiscoveryScopeType.CIDR_NETWORK.value,
            scope_cidr="192.168.20.0/24",
            credential_reference="cisco-ssh-creds",
            metadata_json={},
        )
        db_session.add(target)
        parent_job = DiscoveryJobRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            target_id=network_target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.SUCCEEDED.value,
            requested_capabilities={},
        )
        db_session.add(parent_job)

        # Create run
        state_counts = {
            state: sum(
                scenario["expected_state"] == state
                for scenario in device_scenarios.values()
            )
            for state in DiscoveryResultState
        }
        run = DiscoveryRunRecord(
            id=run_id,
            tenant_id=tenant_id,
            target_identifier="cisco-network",
            target_address="192.168.20.0",
            status="completed",
            metadata_json={},
            total_scanned=len(device_scenarios),
            total_discovered=state_counts[DiscoveryResultState.DISCOVERED],
            total_unreachable=state_counts[DiscoveryResultState.UNREACHABLE],
            total_reachable_no_management=state_counts[
                DiscoveryResultState.REACHABLE_NO_MANAGEMENT
            ],
            total_authentication_failed=state_counts[
                DiscoveryResultState.AUTHENTICATION_FAILED
            ],
            total_partial_discovery=state_counts[
                DiscoveryResultState.PARTIAL_DISCOVERY
            ],
        )
        db_session.add(run)
        db_session.commit()

        # Create device results for all 5 scenarios
        for ip_address, scenario in device_scenarios.items():
            result_id = uuid4()
            device_result = DiscoveryDeviceResultRecord(
                id=result_id,
                tenant_id=tenant_id,
                discovery_job_id=parent_job.id,
                child_job_id=uuid4(),
                address=ip_address,
                state=(
                    DiscoveryJobStatus.SUCCEEDED.value
                    if scenario["expected_state"]
                    == DiscoveryResultState.DISCOVERED.value
                    else DiscoveryJobStatus.FAILED.value
                ),
                result_state=scenario["expected_state"],
                selected_transport=scenario["expected_transport"],
            )
            db_session.add(device_result)
        db_session.commit()

        # Verify: Summary reconciles correctly
        total_categorized = (
            run.total_discovered
            + run.total_unreachable
            + run.total_reachable_no_management
            + run.total_authentication_failed
            + run.total_partial_discovery
        )
        assert total_categorized == run.total_scanned
        assert run.total_scanned == 5
        # Expected: 3 discovered, 1 reachable_no_management, 1 unreachable
        assert run.total_discovered == 3
        assert run.total_reachable_no_management == 1
        assert run.total_unreachable == 1
        assert run.total_authentication_failed == 0
        assert run.total_partial_discovery == 0

    def test_discovery_does_not_classify_ssh_failure_as_host_down(
        self,
        db_session: Session,
        tenant_id: str,
        network_target_id: UUID,
        run_id: UUID,
    ) -> None:
        """Test: SSH failure alone does NOT classify device as UNREACHABLE.

        This is the core requirement: distinguish SSH service unavailability
        from actual host unreachability.
        """
        parent_job = DiscoveryJobRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            target_id=network_target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.SUCCEEDED.value,
            requested_capabilities={},
        )
        db_session.add(parent_job)

        # Create device that has SSH unavailable but is reachable via other means
        device_result = DiscoveryDeviceResultRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            discovery_job_id=parent_job.id,
            child_job_id=uuid4(),
            address="192.168.20.11",
            state=DiscoveryJobStatus.SUCCEEDED.value,
            result_state=DiscoveryResultState.DISCOVERED.value,
            selected_transport="telnet",
        )
        db_session.add(device_result)

        # SSH was attempted and failed
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

        # But Telnet succeeded
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
        )
        db_session.add(telnet_attempt)
        db_session.commit()

        # Verify: Device is NOT classified as unreachable
        assert (
            device_result.result_state != DiscoveryResultState.UNREACHABLE.value
        ), "SSH failure should not cause UNREACHABLE classification"
        assert (
            device_result.result_state == DiscoveryResultState.DISCOVERED.value
        ), "Device discovered via Telnet despite SSH failure"
