"""Bounded multi-device discovery fan-out."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.contracts import (
    DiscoveryFailureCode,
    DiscoveryJobStatus,
    DiscoveryScopeType,
)
from backend.app.discovery.execution import DiscoveryExecutionService
from backend.app.discovery.leases import DISCOVERY_JOB_LEASE_SECONDS
from backend.app.discovery.result_states import DiscoveryResultState
from backend.app.discovery.scopes import DiscoveryScope
from backend.app.persistence.discovery_repositories import (
    DiscoveryCancellationConflictError,
    DiscoveryJobRepository,
)
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryRunStatus,
    DiscoveryTargetRecord,
)


class DiscoveryFanoutService:
    """Expand a scope and execute child jobs with bounded concurrency."""

    def __init__(
        self,
        session: Session,
        collector_registry: CollectorRegistry,
        *,
        concurrency: int = 10,
        max_targets: int = 4096,
    ) -> None:
        if concurrency < 1:
            raise ValueError("Discovery concurrency must be positive.")
        self.session = session
        self.collector_registry = collector_registry
        self.concurrency = concurrency
        self.max_targets = max_targets

    async def execute(
        self,
        *,
        tenant_id: str,
        parent_job_id: UUID,
        execution_owner: UUID | None = None,
        lease_seconds: float = DISCOVERY_JOB_LEASE_SECONDS,
        lease_lost: Callable[[], bool] | None = None,
    ) -> tuple[DiscoveryDeviceResultRecord, ...]:
        effective_owner = execution_owner or uuid4()
        parent = self.session.get(DiscoveryJobRecord, parent_job_id)
        if parent is None or parent.tenant_id != tenant_id:
            raise ValueError("Discovery parent job was not found.")
        target = self.session.get(DiscoveryTargetRecord, parent.target_id)
        if target is None:
            raise ValueError("Discovery scope target was not found.")
        jobs = DiscoveryJobRepository(self.session)
        if jobs.cancellation_requested(tenant_id=tenant_id, job_id=parent_job_id):
            return self.reconcile_parent_job(
                self.session,
                tenant_id=tenant_id,
                parent_job_id=parent_job_id,
                max_targets=self.max_targets,
            )

        addresses = DiscoveryScope(
            scope_type=DiscoveryScopeType(target.scope_type),
            address=target.address,
            scope_end=target.scope_end,
            scope_cidr=target.scope_cidr,
        ).expand(max_targets=self.max_targets)
        self._persist_expected_addresses(parent, addresses)
        self.session.commit()
        children: list[tuple[DiscoveryJobRecord, DiscoveryDeviceResultRecord]] = []
        for address in addresses:
            children.append(self._create_child(tenant_id, parent, target, address))
        self.session.commit()
        semaphore = asyncio.Semaphore(self.concurrency)

        async def run_child(
            child: DiscoveryJobRecord, result: DiscoveryDeviceResultRecord
        ) -> None:
            if jobs.cancellation_requested(tenant_id=tenant_id, job_id=parent_job_id):
                self._cancel_child(parent, child, result)
                return
            async with semaphore:
                if jobs.cancellation_requested(
                    tenant_id=tenant_id, job_id=parent_job_id
                ):
                    self._cancel_child(parent, child, result)
                    return
                result.state = "discovering"
                result.started_at = datetime.now(UTC)
                self.session.commit()
                outcome = await DiscoveryExecutionService(
                    self.session, self.collector_registry
                ).execute(
                    tenant_id=tenant_id,
                    job_id=child.id,
                    parent_job_id=parent_job_id,
                    execution_owner=effective_owner,
                    lease_seconds=lease_seconds,
                    lease_lost=lease_lost,
                )
                self.session.refresh(result)
                result.state = outcome.job.state
                result.selected_transport = outcome.job.selected_transport
                result.failure_code = outcome.job.failure_code
                result.failure_message = outcome.job.failure_message
                result.completed_at = datetime.now(UTC)
                if result.result_state is None:
                    if outcome.job.state == "succeeded":
                        result.result_state = DiscoveryResultState.DISCOVERED.value
                    elif outcome.job.failure_code in {
                        "AUTHENTICATION_FAILED",
                    }:
                        result.result_state = (
                            DiscoveryResultState.AUTHENTICATION_FAILED.value
                        )
                    elif outcome.job.failure_code == "TRANSPORT_UNAVAILABLE":
                        result.result_state = DiscoveryResultState.UNVERIFIED.value
                    elif outcome.job.failure_code in {
                        "CONNECTION_REFUSED",
                        "UNSUPPORTED_CAPABILITY",
                        "UNSUPPORTED_CREDENTIAL",
                        "UNSUPPORTED_PLATFORM",
                    }:
                        result.result_state = (
                            DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value
                        )
                    elif outcome.job.failure_code in {
                        "CONNECTION_FAILED",
                        "CONNECTION_TIMEOUT",
                        "HOST_UNREACHABLE",
                        "DISCOVERY_TIMEOUT",
                    }:
                        result.result_state = DiscoveryResultState.UNREACHABLE.value
                    else:
                        result.result_state = (
                            DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value
                        )
                self.session.commit()

        await asyncio.gather(*(run_child(child, result) for child, result in children))

        self.reconcile_parent_job(
            self.session,
            tenant_id=tenant_id,
            parent_job_id=parent_job_id,
            interrupted=not jobs.cancellation_requested(
                tenant_id=tenant_id, job_id=parent_job_id
            ),
            max_targets=self.max_targets,
        )

        return tuple(result for _, result in children)

    def _cancel_child(
        self,
        parent: DiscoveryJobRecord,
        child: DiscoveryJobRecord,
        result: DiscoveryDeviceResultRecord,
    ) -> None:
        reason = parent.cancellation_reason or "Cancelled by operator."
        requested_by = parent.cancellation_requested_by
        if requested_by is not None:
            try:
                child_job, _ = DiscoveryJobRepository(
                    self.session
                ).request_cancellation(
                    tenant_id=parent.tenant_id,
                    job_id=child.id,
                    requested_by=requested_by,
                    reason=reason,
                )
                result.state = child_job.state
            except DiscoveryCancellationConflictError:
                # A concurrently completed child remains intact.
                return
        else:
            result.state = "cancelled"
        result.failure_code = "CANCELLED"
        result.failure_message = reason
        result.result_state = "cancelled"
        result.completed_at = datetime.now(UTC)
        self.session.commit()

    def _create_child(
        self,
        tenant_id: str,
        parent: DiscoveryJobRecord,
        scope: DiscoveryTargetRecord,
        address: str,
    ) -> tuple[DiscoveryJobRecord, DiscoveryDeviceResultRecord]:
        identifier = f"{scope.identifier}:{address}"
        target = self.session.scalar(
            select(DiscoveryTargetRecord).where(
                DiscoveryTargetRecord.tenant_id == tenant_id,
                DiscoveryTargetRecord.identifier == identifier,
            )
        )
        if target is None:
            try:
                with self.session.begin_nested():
                    new_target = DiscoveryTargetRecord(
                        tenant_id=tenant_id,
                        identifier=identifier,
                        address=address,
                        scope_type="single_device",
                        vendor=scope.vendor,
                        hostname=scope.hostname,
                        platform_hint=scope.platform_hint,
                        preferred_transport=scope.preferred_transport,
                        enabled=scope.enabled,
                        credential_reference=scope.credential_reference,
                        credential_profile_id=scope.credential_profile_id,
                        credential_references=dict(scope.credential_references),
                        allowed_fallback_transports=list(
                            scope.allowed_fallback_transports
                        ),
                        allow_insecure_telnet=bool(
                            getattr(scope, "allow_insecure_telnet", False)
                        ),
                        metadata_json=dict(scope.metadata_json),
                    )
                    self.session.add(new_target)
                    self.session.flush()
                    target = new_target
            except IntegrityError:
                target = self.session.scalar(
                    select(DiscoveryTargetRecord).where(
                        DiscoveryTargetRecord.tenant_id == tenant_id,
                        DiscoveryTargetRecord.identifier == identifier,
                    )
                )
                if target is None:
                    raise
        else:
            target.vendor = scope.vendor
            target.hostname = scope.hostname
            target.platform_hint = scope.platform_hint
            target.preferred_transport = scope.preferred_transport
            target.enabled = scope.enabled
            target.credential_reference = scope.credential_reference
            target.credential_profile_id = scope.credential_profile_id
            target.credential_references = dict(scope.credential_references)
            target.allowed_fallback_transports = list(scope.allowed_fallback_transports)
            target.allow_insecure_telnet = bool(
                getattr(scope, "allow_insecure_telnet", False)
            )
            target.metadata_json = dict(scope.metadata_json)
        run = DiscoveryRunRecord(
            tenant_id=tenant_id,
            target_identifier=target.identifier,
            target_address=address,
            status="started",
            metadata_json={"parent_job_id": str(parent.id)},
        )
        self.session.add(run)
        self.session.flush()
        child = DiscoveryJobRepository(self.session).create(
            tenant_id=tenant_id,
            target_id=target.id,
            run_id=run.id,
            parent_job_id=parent.id,
            requested_capabilities=dict(parent.requested_capabilities),
            timeout_seconds=parent.timeout_seconds,
            correlation_id=str(uuid4()),
        )
        result = DiscoveryDeviceResultRecord(
            tenant_id=tenant_id,
            discovery_job_id=parent.id,
            child_job_id=child.id,
            address=address,
            hostname=scope.hostname,
            vendor=scope.vendor,
            platform=scope.platform_hint,
            state="queued",
            correlation_id=child.correlation_id,
        )
        self.session.add(result)
        self.session.flush()
        return child, result

    def _persist_expected_addresses(
        self, parent: DiscoveryJobRecord, addresses: tuple[str, ...]
    ) -> None:
        if parent.run_id is None:
            return
        run = self.session.get(DiscoveryRunRecord, parent.run_id)
        if run is None:
            return
        metadata = dict(run.metadata_json or {})
        if "expected_addresses" not in metadata:
            metadata["expected_addresses"] = list(addresses)
            self.session.execute(
                update(DiscoveryRunRecord)
                .where(DiscoveryRunRecord.id == parent.run_id)
                .values(metadata_json=metadata)
            )
        self.session.flush()

    @classmethod
    def reconcile_parent_job(
        cls,
        session: Session,
        *,
        tenant_id: str,
        parent_job_id: UUID,
        interrupted: bool = False,
        max_targets: int = 4096,
    ) -> tuple[DiscoveryDeviceResultRecord, ...]:
        """Reconcile durable child outcomes and finalize the parent run."""
        parent = session.get(DiscoveryJobRecord, parent_job_id)
        if parent is None or parent.tenant_id != tenant_id:
            return ()
        target = session.get(DiscoveryTargetRecord, parent.target_id)
        parent_run = session.get(DiscoveryRunRecord, parent.run_id)
        metadata = (
            dict(parent_run.metadata_json or {}) if parent_run is not None else {}
        )
        expected_addresses = tuple(metadata.get("expected_addresses", ()))
        if not expected_addresses and target is not None:
            expected_addresses = DiscoveryScope(
                scope_type=DiscoveryScopeType(target.scope_type),
                address=target.address,
                scope_end=target.scope_end,
                scope_cidr=target.scope_cidr,
            ).expand(max_targets=max_targets)
            metadata["expected_addresses"] = list(expected_addresses)
            if parent_run is not None:
                session.execute(
                    update(DiscoveryRunRecord)
                    .where(DiscoveryRunRecord.id == parent.run_id)
                    .values(metadata_json=metadata)
                )
        if not expected_addresses or target is None:
            return ()
        results = list(
            session.scalars(
                select(DiscoveryDeviceResultRecord).where(
                    DiscoveryDeviceResultRecord.tenant_id == tenant_id,
                    DiscoveryDeviceResultRecord.discovery_job_id == parent_job_id,
                )
            )
        )
        by_address = {result.address: result for result in results}
        outcome_state = "interrupted" if interrupted else "cancelled"
        outcome_code = (
            DiscoveryFailureCode.DISCOVERY_FAILED.value
            if interrupted
            else DiscoveryFailureCode.CANCELLED.value
        )
        outcome_message = (
            "Fan-out execution was interrupted before this address completed."
            if interrupted
            else "Fan-out execution was cancelled before this address completed."
        )

        for address in expected_addresses:
            result = by_address.get(address)
            if result is None:
                _, result = cls(session, CollectorRegistry())._create_child(
                    tenant_id, parent, target, address
                )
                results.append(result)
            child = session.get(DiscoveryJobRecord, result.child_job_id)
            if child is not None and not DiscoveryJobStatus(child.state).is_terminal:
                session.execute(
                    update(DiscoveryJobRecord)
                    .where(
                        DiscoveryJobRecord.id == child.id,
                        DiscoveryJobRecord.tenant_id == tenant_id,
                    )
                    .values(
                        state=(
                            DiscoveryJobStatus.FAILED.value
                            if interrupted
                            else DiscoveryJobStatus.CANCELLED.value
                        ),
                        failure_code=outcome_code,
                        failure_message=outcome_message,
                        completed_at=datetime.now(UTC),
                        execution_owner=None,
                        lease_expires_at=None,
                        last_heartbeat_at=None,
                    )
                )
            if result.result_state is None or result.state in {
                DiscoveryJobStatus.QUEUED.value,
                DiscoveryJobStatus.RUNNING.value,
                "discovering",
            }:
                result.state = (
                    DiscoveryJobStatus.FAILED.value
                    if interrupted
                    else DiscoveryJobStatus.CANCELLED.value
                )
                result.result_state = outcome_state
                result.failure_code = outcome_code
                result.failure_message = outcome_message
                result.completed_at = datetime.now(UTC)

        session.flush()
        cls._finalize_parent_run(
            session,
            parent=parent,
            expected_count=len(expected_addresses),
            results=results,
        )
        session.commit()
        return tuple(results)

    @staticmethod
    def _finalize_parent_run(
        session: Session,
        *,
        parent: DiscoveryJobRecord,
        expected_count: int,
        results: list[DiscoveryDeviceResultRecord],
    ) -> None:
        if parent.run_id is None:
            return
        parent_run = session.get(DiscoveryRunRecord, parent.run_id)
        if parent_run is None:
            return
        counts = Counter(result.result_state for result in results)
        metadata = dict(parent_run.metadata_json or {})
        metadata["summary_calculated"] = True
        metadata["total_cancelled"] = counts.get(
            DiscoveryResultState.CANCELLED.value, 0
        )
        metadata["total_interrupted"] = counts.get(
            DiscoveryResultState.INTERRUPTED.value, 0
        )
        session.execute(
            update(DiscoveryRunRecord)
            .where(DiscoveryRunRecord.id == parent.run_id)
            .values(
                total_scanned=expected_count,
                total_discovered=counts.get(DiscoveryResultState.DISCOVERED.value, 0),
                total_unreachable=counts.get(DiscoveryResultState.UNREACHABLE.value, 0),
                total_reachable_no_management=counts.get(
                    DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value, 0
                ),
                total_authentication_failed=counts.get(
                    DiscoveryResultState.AUTHENTICATION_FAILED.value, 0
                ),
                total_partial_discovery=counts.get(
                    DiscoveryResultState.PARTIAL_DISCOVERY.value, 0
                ),
                total_unverified=counts.get(DiscoveryResultState.UNVERIFIED.value, 0),
                status=(
                    DiscoveryRunStatus.SUCCEEDED.value
                    if counts.get(DiscoveryResultState.DISCOVERED.value, 0) > 0
                    and counts.get(DiscoveryResultState.CANCELLED.value, 0) == 0
                    and counts.get(DiscoveryResultState.INTERRUPTED.value, 0) == 0
                    else DiscoveryRunStatus.FAILED.value
                ),
                finished_at=datetime.now(UTC),
                metadata_json=metadata,
            )
        )


__all__ = ["DiscoveryFanoutService"]
