"""Durable M31.3 discovery execution boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from collections.abc import Callable
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.collectors.base import BaseCollector
from backend.app.collectors.cisco.inventory import CiscoInventoryParser
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.collectors.runtime.processing import process_collector_payload
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryContext, DiscoveryTarget
from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryFailureCode,
    DiscoveryJobStatus,
    DiscoveryTraceability,
)
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.registry import ParserRegistry
from backend.app.persistence.discovery_repositories import (
    DiscoveryEvidenceRepository,
    DiscoveryJobRepository,
    DiscoveryPersistenceError,
    DiscoveryResourceNotFoundError,
    DiscoveryTransportAttemptRepository,
    InvalidDiscoveryTransitionError,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.collectors.base import BaseCollector
from backend.app.collectors.cisco.inventory import CiscoInventoryParser
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.collectors.runtime.processing import process_collector_payload
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryContext, DiscoveryTarget
from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryFailureCode,
    DiscoveryJobStatus,
    DiscoveryTraceability,
)
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.registry import ParserRegistry
from backend.app.persistence.discovery_repositories import (
    DiscoveryEvidenceRepository,
    DiscoveryJobRepository,
    DiscoveryPersistenceError,
    DiscoveryResourceNotFoundError,
    DiscoveryTransportAttemptRepository,
    InvalidDiscoveryTransitionError,
)
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryJobRecord,
    DiscoveryTargetRecord,
    DiscoveryTransportAttemptRecord,
)
from backend.app.persistence.repositories import SnapshotRepository
from backend.app.snapshot.mapper import SnapshotMapper
from backend.app.transports.secret_errors import SecretProviderError


@dataclass(frozen=True, slots=True)
class DiscoveryExecutionOutcome:
    """Durable execution result returned by the service."""

    job: DiscoveryJobRecord
    executed: bool
    evidence_count: int = 0


class DiscoveryCancellationRequestedError(Exception):
    """Internal cooperative cancellation signal for durable discovery."""


class DiscoveryLeaseLostError(Exception):
    """Stop work at a safe boundary after lease renewal fails."""


class DiscoveryExecutionService:
    """Execute raw discovery and persist traceable immutable evidence."""

    def __init__(
        self,
        session: Session,
        collector_registry: CollectorRegistry,
        *,
        parser_pipeline: ParserPipeline | None = None,
        normalization_engine: NormalizationEngine | None = None,
        snapshot_mapper: SnapshotMapper | None = None,
    ) -> None:
        self.session = session
        self.collector_registry = collector_registry
        self.jobs = DiscoveryJobRepository(session)
        self.evidence = DiscoveryEvidenceRepository(session)
        self.attempts = DiscoveryTransportAttemptRepository(session)
        self.parser_pipeline = parser_pipeline or self._default_parser_pipeline()
        self.normalization_engine = normalization_engine or NormalizationEngine()
        self.snapshot_mapper = snapshot_mapper or SnapshotMapper()
        self.snapshots = SnapshotRepository(session)

    @staticmethod
    def _default_parser_pipeline() -> ParserPipeline:
        registry = ParserRegistry()
        registry.register(CiscoInventoryParser())
        return ParserPipeline(registry=registry)

    async def execute(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        parent_job_id: UUID | None = None,
        execution_owner: UUID | None = None,
        lease_seconds: float = 120.0,
        already_claimed: bool = False,
        lease_lost: Callable[[], bool] | None = None,
    ) -> DiscoveryExecutionOutcome:
        """Claim and execute one durable discovery job."""

        effective_owner = execution_owner or uuid4()

        def _check_cancellation() -> None:
            self._raise_if_cancelled(
                tenant_id,
                job_id,
                parent_job_id=parent_job_id,
                lease_lost=lease_lost,
            )

        attempt: DiscoveryTransportAttemptRecord | None = None
        try:
            if already_claimed:
                job = self.jobs.owned_running_job(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    execution_owner=effective_owner,
                )
                if job is None:
                    raise InvalidDiscoveryTransitionError(
                        "Discovery job is not owned by this worker."
                    )
            else:
                job = self.jobs.claim(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    execution_owner=effective_owner,
                    lease_seconds=lease_seconds,
                )
                self.session.commit()
        except InvalidDiscoveryTransitionError as exc:
            self.session.rollback()
            existing = self.jobs.get(tenant_id=tenant_id, job_id=job_id)
            if existing is None:
                raise DiscoveryResourceNotFoundError(
                    "Discovery job was not found."
                ) from exc
            return DiscoveryExecutionOutcome(job=existing, executed=False)

        try:
            target = self._resolve_target(job, tenant_id)
            _check_cancellation()
            if not target.enabled:
                raise DiscoveryExecutionFailureError(
                    DiscoveryFailureCode.TARGET_DISABLED,
                    "Discovery target is disabled.",
                )

            collector, context = self._resolve_collector(
                job,
                target,
                parent_job_id=parent_job_id,
                lease_lost=lease_lost,
            )
            attempt = self._start_transport_attempt(job, target)
            _check_cancellation()
            await collector.health_check(context)
            _check_cancellation()
            raw_payload = await self._collect(collector, context)
            if attempt is not None:
                self.attempts.finish(
                    attempt,
                    result="success",
                )
            self.jobs.record_selection(
                tenant_id=tenant_id,
                job_id=job.id,
                selected_transport=self._payload_string(
                    raw_payload, "transport", target.metadata.get("transport_name")
                ),
                selected_platform=self._payload_string(
                    raw_payload,
                    "platform_family",
                    target.metadata.get("platform_family"),
                ),
            )
            _check_cancellation()
            evidence = self._build_evidence(job, target, collector, raw_payload)
            self.evidence.create(evidence)
            # Raw evidence is an immutable audit artifact and must survive a
            # downstream parser or normalization failure.
            self.session.commit()
            _check_cancellation()
            collector_parser = getattr(collector, "parser", None)
            processed = process_collector_payload(
                parser_pipeline=self.parser_pipeline,
                normalization_engine=self.normalization_engine,
                snapshot_mapper=self.snapshot_mapper,
                source=target.identifier,
                parser_name=getattr(collector_parser, "name", None),
                run_id=job.run_id,
                metadata=dict(context.metadata),
                raw_payload=raw_payload,
            )
            _check_cancellation()
            self.snapshots.add_live_snapshot(
                processed.normalized_result.snapshot,
                discovery_run_id=job.run_id,
            )
            self._record_device_result(
                job=job,
                target=target,
                devices=processed.normalized_result.snapshot.devices,
                selected_transport=self._payload_string(
                    raw_payload, "transport", target.metadata.get("transport_name")
                ),
            )
            _check_cancellation()
            completed = self.jobs.transition(
                tenant_id=tenant_id,
                job_id=job.id,
                target_state=DiscoveryJobStatus.SUCCEEDED,
                require_no_cancellation=True,
                expected_execution_owner=effective_owner,
            )
            self.session.commit()
            return DiscoveryExecutionOutcome(
                job=completed,
                executed=True,
                evidence_count=1,
            )
        except DiscoveryCancellationRequestedError:
            if attempt is not None:
                self.attempts.finish(
                    attempt,
                    result="cancelled",
                    failure_code=DiscoveryFailureCode.CANCELLED.value,
                )
            cancelled = self.jobs.finalise_cancellation(
                tenant_id=tenant_id,
                job_id=job.id,
                expected_execution_owner=effective_owner,
            )
            self.session.commit()
            return DiscoveryExecutionOutcome(job=cancelled, executed=True)
        except DiscoveryLeaseLostError:
            self.session.rollback()
            current = self.jobs.get(tenant_id=tenant_id, job_id=job.id)
            if current is None:
                raise DiscoveryResourceNotFoundError("Discovery job was not found.")
            return DiscoveryExecutionOutcome(job=current, executed=False)
        except Exception as exc:
            if self.jobs.cancellation_requested(tenant_id=tenant_id, job_id=job.id):
                if attempt is not None:
                    self.attempts.finish(
                        attempt,
                        result="cancelled",
                        failure_code=DiscoveryFailureCode.CANCELLED.value,
                    )
                cancelled = self.jobs.finalise_cancellation(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    expected_execution_owner=effective_owner,
                )
                self.session.commit()
                return DiscoveryExecutionOutcome(job=cancelled, executed=True)
            failure_code = self._failure_code(exc)
            failure_message = self._safe_failure_message(exc)
            if attempt is not None:
                self.attempts.finish(
                    attempt,
                    result="failed",
                    failure_code=failure_code.value,
                )
            try:
                failed = self.jobs.mark_failed_after_rollback(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    failure_code=failure_code.value,
                    failure_message=failure_message,
                    expected_execution_owner=effective_owner,
                )
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
            return DiscoveryExecutionOutcome(job=failed, executed=True)

    def _start_transport_attempt(
        self, job: DiscoveryJobRecord, target: DiscoveryTargetRecordView
    ) -> DiscoveryTransportAttemptRecord | None:
        result = self.session.scalar(
            select(DiscoveryDeviceResultRecord).where(
                DiscoveryDeviceResultRecord.child_job_id == job.id,
                DiscoveryDeviceResultRecord.tenant_id == target.tenant_id,
            )
        )
        if result is None:
            return None
        transport = str(target.metadata.get("transport_name", "unknown"))
        return self.attempts.start(
            tenant_id=target.tenant_id,
            device_result_id=result.id,
            transport=transport,
            attempt_order=1,
            correlation_id=job.correlation_id,
        )

    def _resolve_target(
        self, job: DiscoveryJobRecord, tenant_id: str
    ) -> DiscoveryTargetRecordView:
        target = self.jobs.session.get(DiscoveryTargetRecord, job.target_id)
        if target is None or target.tenant_id != tenant_id:
            raise DiscoveryExecutionFailureError(
                DiscoveryFailureCode.TARGET_NOT_FOUND,
                "Discovery target was not found.",
            )
        metadata = dict(target.metadata_json)
        if target.platform_hint is not None:
            metadata.setdefault("platform_family", target.platform_hint)
        if target.preferred_transport is not None:
            metadata.setdefault("transport_name", target.preferred_transport)
        metadata["credential_reference"] = target.credential_reference
        metadata["credential_profile_id"] = target.credential_profile_id
        return DiscoveryTargetRecordView(
            id=target.id,
            tenant_id=target.tenant_id,
            identifier=target.identifier,
            address=target.address,
            enabled=target.enabled,
            metadata=metadata,
        )

    def _resolve_collector(
        self,
        job: DiscoveryJobRecord,
        target: DiscoveryTargetRecordView,
        *,
        parent_job_id: UUID | None = None,
        lease_lost: Callable[[], bool] | None = None,
    ) -> tuple[BaseCollector, CollectorContext]:
        requested = job.requested_capabilities.get("capabilities", ())
        capabilities = frozenset(
            CollectorCapability(str(value))
            for value in requested
            if str(value) in {capability.value for capability in CollectorCapability}
        )
        collector_name = job.requested_capabilities.get("collector_name")
        discovery_target = DiscoveryTarget(
            identifier=target.identifier,
            address=target.address,
            tenant_id=target.tenant_id,
            metadata=target.metadata,
            capabilities=capabilities,
        )
        discovery_context = DiscoveryContext(
            target=discovery_target,
            required_capabilities=capabilities,
            run_id=job.run_id,
            metadata={
                "job_id": str(job.id),
                "cancellation_check": lambda: self._raise_if_cancelled(
                    target.tenant_id,
                    job.id,
                    parent_job_id=parent_job_id,
                    lease_lost=lease_lost,
                ),
            },
        )
        try:
            if isinstance(collector_name, str) and collector_name:
                collector = self.collector_registry.get(collector_name)
            else:
                collectors = self.collector_registry.select(capabilities)
                if not collectors:
                    raise DiscoveryExecutionFailureError(
                        DiscoveryFailureCode.UNSUPPORTED_CAPABILITY,
                        "No collector supports the requested capabilities.",
                    )
                collector = collectors[0]
        except KeyError as exc:
            raise DiscoveryExecutionFailureError(
                DiscoveryFailureCode.UNSUPPORTED_PLATFORM,
                "No supported collector was found for the target.",
            ) from exc
        return collector, collector.build_context(discovery_context)

    @staticmethod
    async def _collect(
        collector: BaseCollector, context: CollectorContext
    ) -> dict[str, object]:
        payload = await collector.collect(context, discovered_targets=())
        return dict(payload)

    def _raise_if_cancelled(
        self,
        tenant_id: str,
        job_id: UUID,
        *,
        parent_job_id: UUID | None = None,
        lease_lost: Callable[[], bool] | None = None,
    ) -> None:
        if lease_lost is not None and lease_lost():
            raise DiscoveryLeaseLostError()
        if self.jobs.cancellation_requested(tenant_id=tenant_id, job_id=job_id):
            raise DiscoveryCancellationRequestedError()
        if parent_job_id is None or not self.jobs.cancellation_requested(
            tenant_id=tenant_id, job_id=parent_job_id
        ):
            return
        parent = self.jobs.get(tenant_id=tenant_id, job_id=parent_job_id)
        if parent is not None and parent.cancellation_requested_by is not None:
            self.jobs.request_cancellation(
                tenant_id=tenant_id,
                job_id=job_id,
                requested_by=parent.cancellation_requested_by,
                reason=parent.cancellation_reason or "Cancelled by operator.",
            )
        raise DiscoveryCancellationRequestedError()

    def _record_device_result(
        self,
        *,
        job: DiscoveryJobRecord,
        target: DiscoveryTargetRecordView,
        devices: tuple[object, ...],
        selected_transport: str | None,
    ) -> None:
        """Create or update the result projection for one executed target."""

        device = devices[0] if devices else None
        existing = self.session.scalar(
            select(DiscoveryDeviceResultRecord).where(
                DiscoveryDeviceResultRecord.child_job_id == job.id,
                DiscoveryDeviceResultRecord.tenant_id == target.tenant_id,
            )
        )
        values = {
            "address": getattr(device, "management_ip", None) or target.address,
            "hostname": getattr(device, "name", None),
            "vendor": getattr(device, "manufacturer", None),
            "platform": getattr(device, "platform", None),
            "state": DiscoveryJobStatus.SUCCEEDED.value,
            "selected_transport": selected_transport,
            "failure_code": None,
            "failure_message": None,
            "completed_at": datetime.now(UTC),
        }
        if existing is None:
            self.session.add(
                DiscoveryDeviceResultRecord(
                    tenant_id=target.tenant_id,
                    discovery_job_id=job.id,
                    child_job_id=job.id,
                    correlation_id=job.correlation_id,
                    started_at=job.started_at,
                    **values,
                )
            )
            return
        for key, value in values.items():
            setattr(existing, key, value)

    @staticmethod
    def _build_evidence(
        job: DiscoveryJobRecord,
        target: DiscoveryTargetRecordView,
        collector: BaseCollector,
        payload: dict[str, object],
    ) -> DiscoveryEvidence:
        transport = payload.get(
            "transport", target.metadata.get("transport_name", "unknown")
        )
        platform = payload.get(
            "platform_family", target.metadata.get("platform_family", "unknown")
        )
        return DiscoveryEvidence(
            traceability=DiscoveryTraceability(
                tenant_id=target.tenant_id,
                target_id=target.id,
                job_id=job.id,
                discovery_run_id=job.run_id,
            ),
            collector_name=collector.name,
            platform=str(platform),
            transport=str(transport),
            evidence_type="raw_discovery",
            command_or_probe="collector.collect",
            payload=payload,
            captured_at=datetime.now(UTC),
            sequence=0,
        )

    @staticmethod
    def _payload_string(
        payload: dict[str, object], key: str, fallback: object | None
    ) -> str | None:
        value = payload.get(key, fallback)
        return None if value is None else str(value)

    @staticmethod
    def _failure_code(exc: Exception) -> DiscoveryFailureCode:
        if isinstance(exc, DiscoveryExecutionFailureError):
            return exc.code
        if isinstance(exc, SecretProviderError):
            return DiscoveryFailureCode.CREDENTIAL_RESOLUTION_FAILED
        if isinstance(exc, asyncio.TimeoutError | TimeoutError):
            return DiscoveryFailureCode.DISCOVERY_TIMEOUT
        if isinstance(exc, DiscoveryPersistenceError):
            return DiscoveryFailureCode.EVIDENCE_PERSISTENCE_FAILED
        message = str(exc).lower()
        if any(
            term in message for term in ("authentication", "unauthorized", "credential")
        ):
            return DiscoveryFailureCode.AUTHENTICATION_FAILED
        if "timeout" in message or "timed out" in message:
            return DiscoveryFailureCode.CONNECTION_TIMEOUT
        if "refused" in message:
            return DiscoveryFailureCode.CONNECTION_REFUSED
        if "transport" in message or "connection" in message:
            return DiscoveryFailureCode.TRANSPORT_UNAVAILABLE
        return DiscoveryFailureCode.DISCOVERY_FAILED

    @staticmethod
    def _safe_failure_message(exc: Exception) -> str:
        message = str(exc).strip()
        return message[:1000] or "Discovery execution failed."


@dataclass(frozen=True, slots=True)
class DiscoveryTargetRecordView:
    """Minimal target data needed after repository resolution."""

    id: UUID
    tenant_id: str
    identifier: str
    address: str
    enabled: bool
    metadata: dict[str, object]


class DiscoveryExecutionFailureError(RuntimeError):
    """Internal typed failure converted to a stable discovery code."""

    def __init__(self, code: DiscoveryFailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


__all__ = [
    "DiscoveryCancellationRequestedError",
    "DiscoveryLeaseLostError",
    "DiscoveryExecutionFailureError",
    "DiscoveryExecutionOutcome",
    "DiscoveryExecutionService",
]
