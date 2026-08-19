"""Durable M31.3 discovery execution boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.collectors.base import BaseCollector
from backend.app.collectors.context import CollectorContext
from backend.app.collectors.registry import CollectorRegistry
from backend.app.discovery.capabilities import CollectorCapability
from backend.app.discovery.context import DiscoveryContext, DiscoveryTarget
from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryFailureCode,
    DiscoveryJobStatus,
    DiscoveryTraceability,
)
from backend.app.persistence.discovery_repositories import (
    DiscoveryEvidenceRepository,
    DiscoveryJobRepository,
    DiscoveryPersistenceError,
    DiscoveryResourceNotFoundError,
    InvalidDiscoveryTransitionError,
)
from backend.app.persistence.models import DiscoveryJobRecord, DiscoveryTargetRecord


@dataclass(frozen=True, slots=True)
class DiscoveryExecutionOutcome:
    """Durable execution result returned by the service."""

    job: DiscoveryJobRecord
    executed: bool
    evidence_count: int = 0


class DiscoveryExecutionService:
    """Execute raw discovery and persist traceable immutable evidence."""

    def __init__(
        self,
        session: Session,
        collector_registry: CollectorRegistry,
    ) -> None:
        self.session = session
        self.collector_registry = collector_registry
        self.jobs = DiscoveryJobRepository(session)
        self.evidence = DiscoveryEvidenceRepository(session)

    async def execute(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
    ) -> DiscoveryExecutionOutcome:
        """Claim and execute one durable discovery job."""

        try:
            job = self.jobs.claim(tenant_id=tenant_id, job_id=job_id)
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
            if not target.enabled:
                raise DiscoveryExecutionFailureError(
                    DiscoveryFailureCode.TARGET_DISABLED,
                    "Discovery target is disabled.",
                )

            collector, context = self._resolve_collector(job, target)
            await collector.health_check(context)
            raw_payload = await self._collect(collector, context)
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
            evidence = self._build_evidence(job, target, collector, raw_payload)
            self.evidence.create(evidence)
            completed = self.jobs.transition(
                tenant_id=tenant_id,
                job_id=job.id,
                target_state=DiscoveryJobStatus.SUCCEEDED,
            )
            self.session.commit()
            return DiscoveryExecutionOutcome(
                job=completed,
                executed=True,
                evidence_count=1,
            )
        except Exception as exc:
            failure_code = self._failure_code(exc)
            failure_message = self._safe_failure_message(exc)
            try:
                failed = self.jobs.mark_failed_after_rollback(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    failure_code=failure_code.value,
                    failure_message=failure_message,
                )
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
            return DiscoveryExecutionOutcome(job=failed, executed=True)

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
            metadata={"job_id": str(job.id)},
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
    "DiscoveryExecutionFailureError",
    "DiscoveryExecutionOutcome",
    "DiscoveryExecutionService",
]
