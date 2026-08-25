"""Bounded multi-device discovery fan-out."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.contracts import DiscoveryScopeType
from backend.app.discovery.execution import DiscoveryExecutionService
from backend.app.discovery.leases import DISCOVERY_JOB_LEASE_SECONDS
from backend.app.discovery.scopes import DiscoveryScope
from backend.app.persistence.discovery_repositories import (
    DiscoveryCancellationConflictError,
    DiscoveryJobRepository,
)
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
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
            return ()

        addresses = DiscoveryScope(
            scope_type=DiscoveryScopeType(target.scope_type),
            address=target.address,
            scope_end=target.scope_end,
            scope_cidr=target.scope_cidr,
        ).expand(max_targets=self.max_targets)
        children: list[tuple[DiscoveryJobRecord, DiscoveryDeviceResultRecord]] = []
        for address in addresses:
            if jobs.cancellation_requested(tenant_id=tenant_id, job_id=parent_job_id):
                break
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
                result.state = outcome.job.state
                result.selected_transport = outcome.job.selected_transport
                result.failure_code = outcome.job.failure_code
                result.failure_message = outcome.job.failure_message
                result.completed_at = datetime.now(UTC)
                self.session.commit()

        await asyncio.gather(*(run_child(child, result) for child, result in children))
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
            target.allowed_fallback_transports = list(
                scope.allowed_fallback_transports
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


__all__ = ["DiscoveryFanoutService"]
