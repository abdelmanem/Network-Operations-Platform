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
from backend.app.discovery.multi_transport import (
    MultiTransportDiscoveryOrchestrator,
    TransportAttemptConfig,
)
from backend.app.discovery.result_states import DiscoveryResultState
from backend.app.discovery.transport_policy import MultiTransportPolicy
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.parsers.registry import ParserRegistry
from backend.app.persistence.discovery_repositories import (
    CredentialProfileRepository,
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
        orchestrator: MultiTransportDiscoveryOrchestrator | None = None,
    ) -> None:
        self.session = session
        self.collector_registry = collector_registry
        self.jobs = DiscoveryJobRepository(session)
        self.evidence = DiscoveryEvidenceRepository(session)
        self.attempts = DiscoveryTransportAttemptRepository(session)
        self.credential_profiles = CredentialProfileRepository(session)
        self.parser_pipeline = parser_pipeline or self._default_parser_pipeline()
        self.normalization_engine = normalization_engine or NormalizationEngine()
        self.snapshot_mapper = snapshot_mapper or SnapshotMapper()
        self.snapshots = SnapshotRepository(session)
        self.orchestrator = orchestrator or MultiTransportDiscoveryOrchestrator(
            enable_service_probing=False,
            allow_reorder_transports=False,
        )

    @staticmethod
    def _default_parser_pipeline() -> ParserPipeline:
        registry = ParserRegistry()
        registry.register(CiscoInventoryParser())
        return ParserPipeline(registry=registry)

    def _resolve_transport_policy(
        self,
        target_view: DiscoveryTargetRecordView,
    ) -> MultiTransportPolicy:
        """Resolve the effective transport policy from credential profile and target.

        Maintains backward compatibility:
        - Legacy SSH-only profiles / no profile → SSH-only policy
        - Profiles with explicit transport_types → ordered policy
        - Telnet is only attempted if allow_insecure_telnet=True on the target
        """
        from backend.app.persistence.models import CredentialProfileRecord

        profile: CredentialProfileRecord | None = None
        allow_insecure = False

        target_metadata = dict(target_view.metadata)
        allow_insecure = bool(target_metadata.get("allow_insecure_telnet", False))

        profile_id_raw = target_metadata.get("credential_profile_id")
        if profile_id_raw:
            try:
                profile_uuid = UUID(str(profile_id_raw))
            except (TypeError, ValueError):
                profile_uuid = None
            if profile_uuid is not None:
                profile = self.credential_profiles.get(
                    tenant_id=target_view.tenant_id,
                    profile_id=profile_uuid,
                )

        if profile is not None:
            policy = MultiTransportPolicy.from_credential_profile(
                profile,
                allow_insecure=allow_insecure,
            )
            if not policy.transports:
                transport_names = ["ssh"]
            else:
                transport_names = [
                    t.transport_name
                    for t in policy.transports
                    if not t.is_insecure or allow_insecure
                ]
                if not transport_names:
                    transport_names = ["ssh"]
        else:
            transport_names = ["ssh"]

        # Also consider target-level fallback transports for backward compat
        fallback = list(target_metadata.get("allowed_fallback_transports") or [])
        if fallback:
            for t in fallback:
                if t not in transport_names:
                    if t == "telnet" and not allow_insecure:
                        continue
                    transport_names.append(t)

        # Remove duplicates preserving order
        seen: set[str] = set()
        ordered: list[str] = []
        for name in transport_names:
            if name not in seen:
                seen.add(name)
                ordered.append(name)

        from backend.app.discovery.transport_policy import (
            CAPABILITY_TO_SERVICE,
            CREDENTIAL_TYPE_COMPATIBILITY,
            INSECURE_TRANSPORTS,
            TransportPolicyEntry,
        )
        from backend.app.transports.base import TransportCapability

        profile_credential_type = (
            profile.credential_type if profile is not None else None
        )

        entries: list[TransportPolicyEntry] = []
        for tname in ordered:
            try:
                cap = TransportCapability(tname.upper())
            except ValueError:
                continue
            svc = CAPABILITY_TO_SERVICE.get(cap)
            if svc is None:
                continue
            is_insecure = cap in INSECURE_TRANSPORTS
            if is_insecure and not allow_insecure:
                continue

            credential_compatible = True
            if profile_credential_type:
                compatible_transports = CREDENTIAL_TYPE_COMPATIBILITY.get(
                    profile_credential_type, []
                )
                credential_compatible = tname.lower() in compatible_transports

            entries.append(
                TransportPolicyEntry(
                    capability=cap,
                    transport_name=tname.lower(),
                    service=svc,
                    is_insecure=is_insecure,
                    credential_compatible=credential_compatible,
                )
            )

        return MultiTransportPolicy(
            transports=tuple(entries),
            allow_insecure=allow_insecure,
            credential_profile_id=str(profile.id) if profile and profile.id else None,
        )

    def _build_transport_configs(
        self,
        job: DiscoveryJobRecord,
        target: DiscoveryTargetRecordView,
        policy: MultiTransportPolicy,
        *,
        parent_job_id: UUID | None = None,
        lease_lost: Callable[[], bool] | None = None,
    ) -> list[TransportAttemptConfig]:
        """Build ordered list of TransportAttemptConfig for fallback."""
        from backend.app.discovery.capabilities import (
            TRANSPORT_TO_COLLECTOR_CAPABILITY,
        )

        requested = job.requested_capabilities.get("capabilities", ())
        requested_name = job.requested_capabilities.get("collector_name")

        configs: list[TransportAttemptConfig] = []
        for entry in policy.transports:
            try:
                if not entry.credential_compatible:
                    self._record_unsupported_credential_attempt(
                        job=job,
                        target=target,
                        transport_name=entry.transport_name,
                        entry=entry,
                    )
                    continue

                if entry.is_insecure and not policy.allow_insecure:
                    continue

                tname_lower = entry.transport_name.lower()
                cap_from_map = TRANSPORT_TO_COLLECTOR_CAPABILITY.get(tname_lower)
                if cap_from_map is not None:
                    collector_caps = frozenset({cap_from_map})
                else:
                    collector_caps = frozenset(
                        CollectorCapability(str(value))
                        for value in requested
                        if str(value)
                        in {cap.value for cap in CollectorCapability}
                    )

                discovery_target = DiscoveryTarget(
                    identifier=f"{target.identifier}:{entry.transport_name}",
                    address=target.address,
                    tenant_id=target.tenant_id,
                    metadata={
                        **dict(target.metadata),
                        "transport_name": entry.transport_name,
                    },
                    capabilities=collector_caps,
                )
                discovery_context = DiscoveryContext(
                    target=discovery_target,
                    required_capabilities=collector_caps,
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

                collector: BaseCollector | None = None
                if isinstance(requested_name, str) and requested_name:
                    try:
                        collector = self.collector_registry.get(requested_name)
                    except KeyError:
                        collector = None
                if collector is None:
                    candidates = self.collector_registry.select(collector_caps)
                    if not candidates:
                        candidates = self.collector_registry.select(frozenset())
                    if candidates:
                        collector = candidates[0]
                if collector is None:
                    continue

                context = collector.build_context(discovery_context)
                configs.append(
                    TransportAttemptConfig(
                        transport_name=entry.transport_name,
                        capability=entry.capability,
                        collector=collector,
                        context=context,
                        is_insecure=entry.is_insecure,
                    )
                )
            except Exception:
                continue
        return configs

    def _record_unsupported_credential_attempt(
        self,
        *,
        job: DiscoveryJobRecord,
        target: DiscoveryTargetRecordView,
        transport_name: str,
        entry: object,
    ) -> None:
        """Record a transport attempt as unsupported_credential for audit."""
        try:
            device_result = self.session.scalar(
                select(DiscoveryDeviceResultRecord).where(
                    DiscoveryDeviceResultRecord.child_job_id == job.id,
                    DiscoveryDeviceResultRecord.tenant_id == target.tenant_id,
                )
            )
            if device_result is None:
                return
            existing = self.session.scalars(
                select(DiscoveryTransportAttemptRecord).where(
                    DiscoveryTransportAttemptRecord.device_result_id
                    == device_result.id,
                    DiscoveryTransportAttemptRecord.transport == transport_name,
                )
            ).first()
            if existing is not None:
                return
            attempt_record = self.attempts.start(
                tenant_id=target.tenant_id,
                device_result_id=device_result.id,
                transport=transport_name,
                attempt_order=0,
                correlation_id=job.correlation_id,
            )
            if attempt_record is not None:
                self.attempts.finish(
                    attempt_record,
                    result="failed",
                    failure_code=DiscoveryFailureCode.UNSUPPORTED_CREDENTIAL.value,
                )
        except Exception:
            pass

    async def _execute_multi_transport(
        self,
        *,
        tenant_id: str,
        job: DiscoveryJobRecord,
        target: DiscoveryTargetRecordView,
        parent_job_id: UUID | None = None,
        lease_lost: Callable[[], bool] | None = None,
    ) -> DiscoveryExecutionOutcome:
        """Execute discovery using multi-transport fallback orchestrator."""
        from backend.app.discovery.contracts import DiscoveryJobStatus

        # 1. Resolve transport policy
        policy = self._resolve_transport_policy(target)

        # 2. Build attempt configs in priority order
        transport_configs = self._build_transport_configs(
            job,
            target,
            policy,
            parent_job_id=parent_job_id,
            lease_lost=lease_lost,
        )

        if not transport_configs:
            raise DiscoveryExecutionFailureError(
                DiscoveryFailureCode.UNSUPPORTED_CAPABILITY,
                "No transport configurations available for the credential profile.",
            )

        # 3. Resolve device_result record to associate attempts with
        device_result = self.session.scalar(
            select(DiscoveryDeviceResultRecord).where(
                DiscoveryDeviceResultRecord.child_job_id == job.id,
                DiscoveryDeviceResultRecord.tenant_id == tenant_id,
            )
        )
        result_started = datetime.now(UTC)
        if device_result is None:
            device_result = DiscoveryDeviceResultRecord(
                tenant_id=tenant_id,
                discovery_job_id=parent_job_id or job.id,
                child_job_id=job.id,
                correlation_id=job.correlation_id,
                address=target.address,
                state=DiscoveryJobStatus.RUNNING.value,
                started_at=result_started,
            )
            self.session.add(device_result)
            self.session.flush()
        else:
            device_result.started_at = result_started
            self.session.flush()

        # 4. Run orchestrator with fallback
        mt_result = await self.orchestrator.discover_with_fallback(
            address=target.address,
            transport_configs=transport_configs,
            attempts_repository=self.attempts,
            device_result=device_result,
            probe_services=False,
        )

        # 5. Persist result_state and state onto device_result
        result_state_value = mt_result.result_state.value
        selected_transport = mt_result.selected_transport

        if device_result is not None:
            device_result.result_state = result_state_value
            device_result.selected_transport = selected_transport
            device_result.completed_at = mt_result.completed_at

        # 6. If discovery was successful → process evidence, snapshot, etc.
        if mt_result.was_discovered and mt_result.discovery_payload is not None:
            last_successful = mt_result.attempts[-1] if mt_result.attempts else None
            try:
                # Persist successful transport selection on the job record
                self.jobs.record_selection(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    selected_transport=selected_transport,
                    selected_platform=self._payload_string(
                        mt_result.discovery_payload,
                        "platform_family",
                        target.metadata.get("platform_family"),
                    ),
                )
                self._raise_if_cancelled(
                    tenant_id, job.id, parent_job_id=parent_job_id, lease_lost=lease_lost
                )

                # Use last successful attempt's collector (if available) for metadata
                # Fallback to any registered collector for evidence naming
                collector_for_evidence = transport_configs[-1].collector
                for cfg in transport_configs:
                    if cfg.transport_name == selected_transport:
                        collector_for_evidence = cfg.collector
                        break

                evidence = self._build_evidence(
                    job,
                    target,
                    collector_for_evidence,
                    mt_result.discovery_payload,
                )
                self.evidence.create(evidence)
                self.session.commit()

                self._raise_if_cancelled(
                    tenant_id, job.id, parent_job_id=parent_job_id, lease_lost=lease_lost
                )

                collector_parser = getattr(collector_for_evidence, "parser", None)
                processed = process_collector_payload(
                    parser_pipeline=self.parser_pipeline,
                    normalization_engine=self.normalization_engine,
                    snapshot_mapper=self.snapshot_mapper,
                    source=target.identifier,
                    parser_name=getattr(collector_parser, "name", None),
                    run_id=job.run_id,
                    metadata=dict(target.metadata),
                    raw_payload=mt_result.discovery_payload,
                )
                self._raise_if_cancelled(
                    tenant_id, job.id, parent_job_id=parent_job_id, lease_lost=lease_lost
                )

                self.snapshots.add_live_snapshot(
                    processed.normalized_result.snapshot,
                    discovery_run_id=job.run_id,
                )
                self._record_device_result(
                    job=job,
                    target=target,
                    devices=processed.normalized_result.snapshot.devices,
                    selected_transport=selected_transport,
                    result_state=result_state_value,
                )

                completed = self.jobs.transition(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    target_state=DiscoveryJobStatus.SUCCEEDED,
                    require_no_cancellation=True,
                )
                self.session.commit()
                if device_result is not None:
                    device_result.state = DiscoveryJobStatus.SUCCEEDED.value
                    self.session.flush()
                return DiscoveryExecutionOutcome(
                    job=completed,
                    executed=True,
                    evidence_count=1,
                )
            except DiscoveryCancellationRequestedError:
                raise
            except DiscoveryLeaseLostError:
                raise
            except Exception:
                # Evidence was already committed; fall through to failure handling
                pass

        # 7. Failure path - set appropriate failure state based on result_state
        if device_result is not None:
            device_result.state = DiscoveryJobStatus.FAILED.value

        # Determine failure_code and message from the worst attempt
        failure_code = DiscoveryFailureCode.DISCOVERY_FAILED
        failure_message = "Discovery did not complete successfully."
        last_failure = None
        for attempt in reversed(mt_result.attempts):
            if not attempt.success and attempt.failure_code is not None:
                last_failure = attempt
                break
        if last_failure is not None and last_failure.failure_code is not None:
            failure_code = last_failure.failure_code
            if last_failure.failure_message:
                failure_message = last_failure.failure_message

        # Map result_state for cases not covered by attempt failures
        if mt_result.result_state == DiscoveryResultState.UNREACHABLE:
            failure_code = DiscoveryFailureCode.CONNECTION_FAILED
            failure_message = "Host was unreachable for all configured transports."
        elif mt_result.result_state == DiscoveryResultState.REACHABLE_NO_MANAGEMENT:
            failure_code = DiscoveryFailureCode.TRANSPORT_UNAVAILABLE
            failure_message = "Host is reachable but no configured management transport succeeded."
        elif mt_result.result_state == DiscoveryResultState.AUTHENTICATION_FAILED:
            failure_code = DiscoveryFailureCode.AUTHENTICATION_FAILED
            failure_message = "Authentication failed for all applicable management transports."
        elif mt_result.result_state == DiscoveryResultState.PARTIAL_DISCOVERY:
            failure_code = DiscoveryFailureCode.DISCOVERY_FAILED
            failure_message = "Partial discovery data collected but full discovery did not complete."

        if device_result is not None:
            device_result.failure_code = failure_code.value
            device_result.failure_message = failure_message
            device_result.result_state = result_state_value

        failed = self.jobs.mark_failed_after_rollback(
            tenant_id=tenant_id,
            job_id=job.id,
            failure_code=failure_code.value,
            failure_message=failure_message,
        )
        self.session.commit()
        return DiscoveryExecutionOutcome(job=failed, executed=True)

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

            has_profile = target.metadata.get("credential_profile_id") is not None
            has_fallback = bool(target.metadata.get("allowed_fallback_transports"))
            if has_profile or has_fallback:
                return await self._execute_multi_transport(
                    tenant_id=tenant_id,
                    job=job,
                    target=target,
                    parent_job_id=parent_job_id,
                    lease_lost=lease_lost,
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
                result_state="DISCOVERED",
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
            # Ensure device_result record exists for cancelled discoveries
            try:
                resolved_target = self._resolve_target(job, tenant_id)
                device_result = self.session.scalar(
                    select(DiscoveryDeviceResultRecord).where(
                        DiscoveryDeviceResultRecord.child_job_id == job.id,
                        DiscoveryDeviceResultRecord.tenant_id == resolved_target.tenant_id,
                    )
                )
                if device_result is None:
                    device_result = DiscoveryDeviceResultRecord(
                        tenant_id=resolved_target.tenant_id,
                        discovery_job_id=job.id,
                        child_job_id=job.id,
                        correlation_id=job.correlation_id,
                        address=resolved_target.address,
                        state=DiscoveryJobStatus.CANCELLED.value,
                        started_at=job.started_at or datetime.now(UTC),
                        completed_at=datetime.now(UTC),
                        result_state=DiscoveryResultState.UNREACHABLE.value,
                    )
                    self.session.add(device_result)
                    self.session.flush()
                else:
                    device_result.state = DiscoveryJobStatus.CANCELLED.value
                    device_result.completed_at = datetime.now(UTC)
                    self.session.flush()
            except Exception:
                # If we can't create device_result, don't let it stop cancellation
                pass
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
            resolved_target = self._resolve_target(job, tenant_id)
            try:
                failed = self.jobs.mark_failed_after_rollback(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    failure_code=failure_code.value,
                    failure_message=failure_message,
                    expected_execution_owner=effective_owner,
                )
                # Persist the device result after rollback has cleared pending work.
                self._ensure_device_result_for_failure(
                    job=job,
                    target=resolved_target,
                    failure_code=failure_code,
                    failure_message=failure_message,
                    selected_transport=str(
                        resolved_target.metadata.get("transport_name", "unknown")
                    ),
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
            result = DiscoveryDeviceResultRecord(
                tenant_id=target.tenant_id,
                discovery_job_id=job.id,
                child_job_id=job.id,
                correlation_id=job.correlation_id,
                address=target.address,
                state=DiscoveryJobStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
            self.session.add(result)
            self.session.flush()
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
        metadata["allow_insecure_telnet"] = bool(
            getattr(target, "allow_insecure_telnet", False)
        )
        metadata.setdefault(
            "allowed_fallback_transports",
            list(target.allowed_fallback_transports or []),
        )
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

    def _ensure_device_result_for_failure(
        self,
        *,
        job: DiscoveryJobRecord,
        target: DiscoveryTargetRecordView,
        failure_code: DiscoveryFailureCode,
        failure_message: str | None = None,
        selected_transport: str | None = None,
    ) -> DiscoveryDeviceResultRecord | None:
        """Ensure a device_result record exists and set appropriate failure state.

        This method guarantees a device_result record exists for all execution paths
        and maps the failure code to the appropriate result_state classification.
        """
        from backend.app.discovery.result_states import DiscoveryResultState

        existing = self.session.scalar(
            select(DiscoveryDeviceResultRecord).where(
                DiscoveryDeviceResultRecord.child_job_id == job.id,
                DiscoveryDeviceResultRecord.tenant_id == target.tenant_id,
            )
        )

        # Map failure code to result_state
        result_state = DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value
        if failure_code in {
            DiscoveryFailureCode.CONNECTION_FAILED,
            DiscoveryFailureCode.CONNECTION_TIMEOUT,
            DiscoveryFailureCode.HOST_UNREACHABLE,
            DiscoveryFailureCode.DISCOVERY_TIMEOUT,
        }:
            result_state = DiscoveryResultState.UNREACHABLE.value
        elif failure_code in {
            DiscoveryFailureCode.AUTHENTICATION_FAILED,
        }:
            result_state = DiscoveryResultState.AUTHENTICATION_FAILED.value
        elif failure_code in {
            DiscoveryFailureCode.CONNECTION_REFUSED,
            DiscoveryFailureCode.TRANSPORT_UNAVAILABLE,
            DiscoveryFailureCode.UNSUPPORTED_CAPABILITY,
            DiscoveryFailureCode.UNSUPPORTED_CREDENTIAL,
            DiscoveryFailureCode.UNSUPPORTED_PLATFORM,
        }:
            result_state = DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value
        else:
            result_state = DiscoveryResultState.REACHABLE_NO_MANAGEMENT.value

        values = {
            "address": target.address,
            "state": DiscoveryJobStatus.FAILED.value,
            "result_state": result_state,
            "selected_transport": selected_transport,
            "failure_code": failure_code.value,
            "failure_message": failure_message,
            "completed_at": datetime.now(UTC),
        }

        if existing is None:
            existing = DiscoveryDeviceResultRecord(
                tenant_id=target.tenant_id,
                discovery_job_id=job.id,
                child_job_id=job.id,
                correlation_id=job.correlation_id,
                started_at=job.started_at or datetime.now(UTC),
                **values,
            )
            self.session.add(existing)
            self.session.flush()
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            self.session.flush()

        return existing

    def _record_device_result(
        self,
        *,
        job: DiscoveryJobRecord,
        target: DiscoveryTargetRecordView,
        devices: tuple[object, ...],
        selected_transport: str | None,
        result_state: str | None = None,
    ) -> None:
        """Create or update the result projection for one executed target."""
        from backend.app.discovery.result_states import DiscoveryResultState

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
            "result_state": result_state or DiscoveryResultState.DISCOVERED.value,
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

    @classmethod
    def _sanitize_payload(cls, data: object) -> object:
        """Recursively redact secrets, passwords, and tokens from evidence payload."""
        import re

        sensitive_key_pattern = re.compile(
            r"(password|secret|token|credential|api_key|auth_pass|enable_pass|community)",
            re.IGNORECASE,
        )
        if isinstance(data, dict):
            sanitized: dict[str, object] = {}
            for k, v in data.items():
                if isinstance(k, str) and sensitive_key_pattern.search(k):
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = cls._sanitize_payload(v)
            return sanitized
        elif isinstance(data, list):
            return [cls._sanitize_payload(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(cls._sanitize_payload(item) for item in data)
        elif isinstance(data, str):
            # Also sanitize common CLI password patterns in raw command output lines
            # e.g., "password SecretP@ss", "secret mySecretEnablePass"
            sanitized_str = re.sub(
                r"(password|secret)\s+([^\s]+)",
                r"\1 [REDACTED]",
                data,
                flags=re.IGNORECASE,
            )
            return sanitized_str
        return data

    @classmethod
    def _build_evidence(
        cls,
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
        sanitized_payload = cls._sanitize_payload(payload)
        if not isinstance(sanitized_payload, dict):
            sanitized_payload = {"data": sanitized_payload}
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
            payload=sanitized_payload,
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
