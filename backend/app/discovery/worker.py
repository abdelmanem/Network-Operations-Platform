"""Durable in-process discovery job worker.

The worker is not bound to HTTP tenant context. It discovers queued root jobs
and expired owned leases across tenants, then performs every claim, heartbeat,
recovery, and completion update with an explicit tenant_id.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.execution import DiscoveryExecutionService
from backend.app.discovery.fanout import DiscoveryFanoutService
from backend.app.discovery.leases import (
    DISCOVERY_JOB_CLAIM_LIMIT,
    DISCOVERY_JOB_HEARTBEAT_INTERVAL_SECONDS,
    DISCOVERY_JOB_LEASE_SECONDS,
    DISCOVERY_JOB_POLL_INTERVAL_SECONDS,
    HEARTBEAT_LOST_MESSAGE,
    PROTECTED_DISCOVERY_JOB_ID,
)
from backend.app.discovery.contracts import (
    DiscoveryFailureCode,
    DiscoveryJobStatus,
)
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.persistence.discovery_repositories import (
    DiscoveryJobRepository,
    DiscoveryTargetRepository,
    InvalidDiscoveryTransitionError,
)
from backend.app.persistence.models import DiscoveryJobRecord


def pytest_worker_disabled() -> bool:
    """Keep TestClient/app construction from claiming live jobs."""

    return os.environ.get("PYTEST_CURRENT_TEST") is not None


@dataclass(slots=True)
class DiscoveryJobWorker:
    """Poll, claim, heartbeat, and execute durable discovery jobs."""

    session_factory: Callable[[], Session]
    collector_registry: CollectorRegistry
    parser_pipeline: ParserPipeline
    normalization_engine: NormalizationEngine
    lease_seconds: float = DISCOVERY_JOB_LEASE_SECONDS
    heartbeat_interval_seconds: float = DISCOVERY_JOB_HEARTBEAT_INTERVAL_SECONDS
    poll_interval_seconds: float = DISCOVERY_JOB_POLL_INTERVAL_SECONDS
    claim_limit: int = DISCOVERY_JOB_CLAIM_LIMIT
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))
    _stop: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.heartbeat_interval_seconds * 2 >= self.lease_seconds:
            raise ValueError(
                "Discovery heartbeat interval must be less than half the lease."
            )

    def start(self) -> asyncio.Task[None]:
        """Start the worker loop as a tracked asyncio task."""

        self._stop = asyncio.Event()
        self._task = asyncio.create_task(self.run(), name="discovery-job-worker")
        return self._task

    async def stop(self) -> None:
        """Request cooperative shutdown and wait for in-flight work."""

        self._stop.set()
        if self._task is None:
            return
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def run(self) -> None:
        """Recover expired owned work, then claim and execute queued roots."""

        while not self._stop.is_set():
            try:
                self.recover_expired_jobs()
                claimed = self.claim_queued_jobs()
            except Exception:
                self.logger.exception("Discovery worker poll failed")
                claimed = ()
            if claimed:
                await asyncio.gather(
                    *(
                        self._run_owned_job(tenant_id, job_id, owner)
                        for tenant_id, job_id, owner in claimed
                    )
                )
                continue
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.poll_interval_seconds
                )
            except TimeoutError:
                continue

    def recover_expired_jobs(self) -> None:
        """Fail or cancel expired owned root jobs. Never resume them."""

        session = self.session_factory()
        try:
            jobs = DiscoveryJobRepository(session)
            expired = jobs.recover_expired_owned_jobs(stale_before=datetime.now(UTC))
        finally:
            session.close()
        for tenant_id, job_id in expired:
            if job_id == PROTECTED_DISCOVERY_JOB_ID:
                continue
            session = self.session_factory()
            try:
                DiscoveryJobRepository(session).recover_expired_owned_job(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    stale_before=datetime.now(UTC),
                )
                session.commit()
            except Exception:
                session.rollback()
                self.logger.exception(
                    "Discovery worker recovery failed for %s/%s", tenant_id, job_id
                )
            finally:
                session.close()

    def claim_queued_jobs(self) -> tuple[tuple[str, UUID, UUID], ...]:
        """Atomically claim queued roots. Returns tenant-scoped owned jobs."""

        session = self.session_factory()
        try:
            candidates = DiscoveryJobRepository(session).list_queued_roots(
                limit=self.claim_limit
            )
        finally:
            session.close()

        claimed: list[tuple[str, UUID, UUID]] = []
        for tenant_id, job_id in candidates:
            if job_id == PROTECTED_DISCOVERY_JOB_ID:
                continue
            owner = uuid4()
            session = self.session_factory()
            try:
                DiscoveryJobRepository(session).claim(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    execution_owner=owner,
                    lease_seconds=self.lease_seconds,
                )
                session.commit()
            except InvalidDiscoveryTransitionError:
                session.rollback()
                continue
            except Exception:
                session.rollback()
                self.logger.exception(
                    "Discovery worker claim failed for %s/%s", tenant_id, job_id
                )
                continue
            finally:
                session.close()
            claimed.append((tenant_id, job_id, owner))
        return tuple(claimed)

    async def _run_owned_job(
        self, tenant_id: str, job_id: UUID, execution_owner: UUID
    ) -> None:
        heartbeat_lease_lost = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._heartbeat(tenant_id, job_id, execution_owner, heartbeat_lease_lost),
            name=f"discovery-heartbeat-{job_id}",
        )
        try:
            await execute_discovery_job(
                session_factory=self.session_factory,
                collector_registry=self.collector_registry,
                parser_pipeline=self.parser_pipeline,
                normalization_engine=self.normalization_engine,
                tenant_id=tenant_id,
                job_id=job_id,
                execution_owner=execution_owner,
                lease_seconds=self.lease_seconds,
                already_claimed=True,
                lease_lost=lambda: heartbeat_lease_lost.is_set() or self._stop.is_set(),
            )
        except Exception as exc:
            self.logger.exception(
                "Discovery worker execution failed for %s/%s", tenant_id, job_id
            )
            if not heartbeat_lease_lost.is_set():
                self._fail_owned_job(tenant_id, job_id, execution_owner, exc)
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            if heartbeat_lease_lost.is_set():
                self._abandon_if_owned(tenant_id, job_id, execution_owner)

    async def _heartbeat(
        self,
        tenant_id: str,
        job_id: UUID,
        execution_owner: UUID,
        lease_lost: asyncio.Event,
    ) -> None:
        while not lease_lost.is_set() and not self._stop.is_set():
            try:
                await asyncio.sleep(self.heartbeat_interval_seconds)
                if lease_lost.is_set() or self._stop.is_set():
                    return
                session = self.session_factory()
                try:
                    renewed = DiscoveryJobRepository(session).renew_lease(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        execution_owner=execution_owner,
                        lease_seconds=self.lease_seconds,
                    )
                    session.commit()
                finally:
                    session.close()
                if not renewed:
                    lease_lost.set()
                    self._abandon_if_owned(tenant_id, job_id, execution_owner)
                    return
            except asyncio.CancelledError:
                raise
            except Exception:
                lease_lost.set()
                self.logger.exception(
                    "Discovery worker heartbeat failed for %s/%s", tenant_id, job_id
                )
                self._abandon_if_owned(tenant_id, job_id, execution_owner)
                return

    def _fail_owned_job(
        self,
        tenant_id: str,
        job_id: UUID,
        execution_owner: UUID,
        exc: Exception,
    ) -> None:
        session = self.session_factory()
        try:
            jobs = DiscoveryJobRepository(session)
            current = jobs.get(tenant_id=tenant_id, job_id=job_id)
            if current is None or current.state != DiscoveryJobStatus.RUNNING.value:
                return
            if current.execution_owner != execution_owner:
                return
            failure_code = DiscoveryFailureCode.DISCOVERY_FAILED.value
            failure_message = str(exc).strip() or "Discovery execution failed."
            jobs.transition(
                tenant_id=tenant_id,
                job_id=job_id,
                target_state=DiscoveryJobStatus.FAILED,
                failure_code=failure_code,
                failure_message=failure_message[:1000],
                expected_execution_owner=execution_owner,
            )
            target = DiscoveryTargetRepository(session).get(
                tenant_id=tenant_id, target_id=current.target_id
            )
            if target is not None and target.scope_type in {"ip_range", "cidr_network"}:
                DiscoveryFanoutService.reconcile_parent_job(
                    session,
                    tenant_id=tenant_id,
                    parent_job_id=job_id,
                    interrupted=True,
                )
            else:
                session.commit()
        except Exception:
            session.rollback()
            self.logger.exception(
                "Discovery worker failed to transition errored job for %s/%s",
                tenant_id,
                job_id,
            )
        finally:
            session.close()

    def _abandon_if_owned(
        self, tenant_id: str, job_id: UUID, execution_owner: UUID
    ) -> None:
        session = self.session_factory()
        try:
            DiscoveryJobRepository(session).abandon_owned_job(
                tenant_id=tenant_id,
                job_id=job_id,
                execution_owner=execution_owner,
                failure_message=HEARTBEAT_LOST_MESSAGE,
            )
            session.commit()
        except Exception:
            session.rollback()
            self.logger.exception(
                "Discovery worker abandon failed for %s/%s", tenant_id, job_id
            )
        finally:
            session.close()


async def execute_discovery_job(
    *,
    session_factory: Callable[[], Session],
    collector_registry: CollectorRegistry,
    parser_pipeline: ParserPipeline,
    normalization_engine: NormalizationEngine,
    tenant_id: str,
    job_id: UUID,
    execution_owner: UUID,
    lease_seconds: float,
    already_claimed: bool = False,
    lease_lost: Callable[[], bool] | None = None,
) -> DiscoveryJobRecord | None:
    """Run one claimed root job through the existing execution engines."""

    db_session = session_factory()
    try:
        jobs = DiscoveryJobRepository(db_session)
        job = jobs.get(tenant_id=tenant_id, job_id=job_id)
        if job is None or job.state == DiscoveryJobStatus.CANCELLED.value:
            return job
        target = DiscoveryTargetRepository(db_session).get(
            tenant_id=tenant_id, target_id=job.target_id
        )
        if target is not None and target.scope_type in {"ip_range", "cidr_network"}:
            try:
                if not already_claimed:
                    jobs.claim(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        execution_owner=execution_owner,
                        lease_seconds=lease_seconds,
                    )
                    db_session.commit()
                results = await DiscoveryFanoutService(
                    db_session, collector_registry, concurrency=10
                ).execute(
                    tenant_id=tenant_id,
                    parent_job_id=job_id,
                    execution_owner=execution_owner,
                    lease_seconds=lease_seconds,
                    lease_lost=lease_lost,
                )
                if jobs.cancellation_requested(tenant_id=tenant_id, job_id=job_id):
                    jobs.finalise_cancellation(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        expected_execution_owner=execution_owner,
                    )
                else:
                    final_state = (
                        DiscoveryJobStatus.SUCCEEDED
                        if any(result.state == "succeeded" for result in results)
                        else DiscoveryJobStatus.FAILED
                    )
                    jobs.transition(
                        tenant_id=tenant_id,
                        job_id=job_id,
                        target_state=final_state,
                        require_no_cancellation=True,
                        expected_execution_owner=execution_owner,
                    )
                db_session.commit()
            except InvalidDiscoveryTransitionError:
                db_session.rollback()
                current = jobs.get(tenant_id=tenant_id, job_id=job_id)
                if current is not None and current.state == (
                    DiscoveryJobStatus.CANCELLED.value
                ):
                    return current
                if not jobs.cancellation_requested(tenant_id=tenant_id, job_id=job_id):
                    raise
                jobs.finalise_cancellation(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    expected_execution_owner=execution_owner,
                )
                db_session.commit()
            return jobs.get(tenant_id=tenant_id, job_id=job_id)
        service = DiscoveryExecutionService(
            db_session,
            collector_registry,
            parser_pipeline=parser_pipeline,
            normalization_engine=normalization_engine,
        )
        outcome = await service.execute(
            tenant_id=tenant_id,
            job_id=job_id,
            execution_owner=execution_owner,
            lease_seconds=lease_seconds,
            already_claimed=already_claimed,
            lease_lost=lease_lost,
        )
        return outcome.job
    finally:
        db_session.close()
