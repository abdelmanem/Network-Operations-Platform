"""Repositories for the M31 discovery persistence boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryJobStatus,
    transition_job,
)
from backend.app.persistence.models import (
    DiscoveryEvidenceRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)


class DiscoveryPersistenceError(RuntimeError):
    """Base error for discovery persistence operations."""


class DuplicateActiveDiscoveryError(DiscoveryPersistenceError):
    """Raised when a target already has an active discovery job."""


class DiscoveryResourceNotFoundError(DiscoveryPersistenceError):
    """Raised when a tenant-scoped discovery resource is unavailable."""


class InvalidDiscoveryTransitionError(DiscoveryPersistenceError):
    """Raised when a job transition violates the M31 state machine."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_payload(payload).encode("utf-8")).hexdigest()


class DiscoveryTargetRepository:
    """Tenant-scoped repository for discovery target configuration."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        tenant_id: str,
        identifier: str,
        address: str,
        credential_reference: str,
        platform_hint: str | None = None,
        preferred_transport: str | None = None,
        enabled: bool = True,
        metadata: dict[str, object] | None = None,
        created_by: UUID | None = None,
    ) -> DiscoveryTargetRecord:
        record = DiscoveryTargetRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            identifier=identifier,
            address=address,
            platform_hint=platform_hint,
            preferred_transport=preferred_transport,
            enabled=enabled,
            credential_reference=credential_reference,
            metadata_json={} if metadata is None else dict(metadata),
            created_by=created_by,
        )
        self.session.add(record)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise DiscoveryPersistenceError(
                "A target with this identifier already exists for the tenant."
            ) from exc
        return record

    def get(self, *, tenant_id: str, target_id: UUID) -> DiscoveryTargetRecord | None:
        statement = select(DiscoveryTargetRecord).where(
            DiscoveryTargetRecord.id == target_id,
            DiscoveryTargetRecord.tenant_id == tenant_id,
        )
        return self.session.scalars(statement).first()

    def list(self, *, tenant_id: str) -> tuple[DiscoveryTargetRecord, ...]:
        statement = (
            select(DiscoveryTargetRecord)
            .where(DiscoveryTargetRecord.tenant_id == tenant_id)
            .order_by(DiscoveryTargetRecord.created_at.desc())
        )
        return tuple(self.session.scalars(statement).all())


class DiscoveryJobRepository:
    """Tenant-scoped repository for durable discovery jobs."""

    _ACTIVE_STATES = (
        DiscoveryJobStatus.QUEUED.value,
        DiscoveryJobStatus.RUNNING.value,
    )

    def __init__(self, session: Session) -> None:
        self.session = session

    def _lock_target(self, tenant_id: str, target_id: UUID) -> None:
        """Serialize one tenant/target boundary on PostgreSQL."""

        bind = self.session.get_bind()
        if bind.dialect.name == "postgresql":
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"discovery:{tenant_id}:{target_id}"},
            )

    def create(
        self,
        *,
        tenant_id: str,
        target_id: UUID,
        run_id: UUID,
        created_by: UUID | None = None,
        requested_capabilities: dict[str, object] | None = None,
        timeout_seconds: float | None = None,
        correlation_id: str | None = None,
    ) -> DiscoveryJobRecord:
        target = self.session.get(DiscoveryTargetRecord, target_id)
        run = self.session.get(DiscoveryRunRecord, run_id)
        if target is None or target.tenant_id != tenant_id:
            raise DiscoveryResourceNotFoundError("Discovery target was not found.")
        if run is None or run.tenant_id not in {None, tenant_id}:
            raise DiscoveryResourceNotFoundError("Discovery run was not found.")
        self._lock_target(tenant_id, target_id)
        active = self.session.scalars(
            select(DiscoveryJobRecord.id).where(
                DiscoveryJobRecord.tenant_id == tenant_id,
                DiscoveryJobRecord.target_id == target_id,
                DiscoveryJobRecord.state.in_(self._ACTIVE_STATES),
            )
        ).first()
        if active is not None:
            raise DuplicateActiveDiscoveryError(
                "A discovery execution is already active for this target."
            )

        record = DiscoveryJobRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            target_id=target_id,
            run_id=run_id,
            state=DiscoveryJobStatus.QUEUED.value,
            created_by=created_by,
            requested_capabilities=(
                {} if requested_capabilities is None else dict(requested_capabilities)
            ),
            timeout_seconds=timeout_seconds,
            correlation_id=correlation_id,
        )
        self.session.add(record)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise DuplicateActiveDiscoveryError(
                "A discovery execution is already active for this target."
            ) from exc
        return record

    def get(self, *, tenant_id: str, job_id: UUID) -> DiscoveryJobRecord | None:
        statement = select(DiscoveryJobRecord).where(
            DiscoveryJobRecord.id == job_id,
            DiscoveryJobRecord.tenant_id == tenant_id,
        )
        return self.session.scalars(statement).first()

    def list(self, *, tenant_id: str) -> tuple[DiscoveryJobRecord, ...]:
        statement = (
            select(DiscoveryJobRecord)
            .where(DiscoveryJobRecord.tenant_id == tenant_id)
            .order_by(DiscoveryJobRecord.requested_at.desc())
        )
        return tuple(self.session.scalars(statement).all())

    def claim(self, *, tenant_id: str, job_id: UUID) -> DiscoveryJobRecord:
        """Atomically transition one queued job to running."""

        job = self.get(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            raise DiscoveryResourceNotFoundError("Discovery job was not found.")
        self._lock_target(tenant_id, job.target_id)
        now = _utc_now()
        result = cast(
            CursorResult[Any],
            self.session.execute(
                update(DiscoveryJobRecord)
                .where(
                    DiscoveryJobRecord.id == job_id,
                    DiscoveryJobRecord.tenant_id == tenant_id,
                    DiscoveryJobRecord.state == DiscoveryJobStatus.QUEUED.value,
                )
                .values(
                    state=DiscoveryJobStatus.RUNNING.value,
                    started_at=now,
                    updated_at=now,
                    attempts=DiscoveryJobRecord.attempts + 1,
                )
            ),
        )
        if result.rowcount != 1:
            self.session.rollback()
            raise InvalidDiscoveryTransitionError(
                "Only queued discovery jobs can be claimed."
            )
        self.session.flush()
        return self.get(tenant_id=tenant_id, job_id=job_id)  # type: ignore[return-value]

    def transition(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        target_state: DiscoveryJobStatus,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> DiscoveryJobRecord:
        """Apply one validated durable state transition."""

        job = self.get(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            raise DiscoveryResourceNotFoundError("Discovery job was not found.")
        try:
            transition_job(DiscoveryJobStatus(job.state), target_state)
        except (KeyError, ValueError) as exc:
            raise InvalidDiscoveryTransitionError(str(exc)) from exc

        now = _utc_now()
        values: dict[str, object] = {"state": target_state.value, "updated_at": now}
        if target_state.is_terminal:
            values["completed_at"] = now
        if failure_code is not None:
            values["failure_code"] = failure_code
        if failure_message is not None:
            values["failure_message"] = failure_message
        self.session.execute(
            update(DiscoveryJobRecord)
            .where(
                DiscoveryJobRecord.id == job_id,
                DiscoveryJobRecord.tenant_id == tenant_id,
                DiscoveryJobRecord.state == job.state,
            )
            .values(**values)
        )
        self.session.flush()
        return self.get(tenant_id=tenant_id, job_id=job_id)  # type: ignore[return-value]

    def mark_failed_after_rollback(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        failure_code: str,
        failure_message: str,
    ) -> DiscoveryJobRecord:
        """Rollback pending work, then persist failure in a clean transaction."""

        self.session.rollback()
        return self.transition(
            tenant_id=tenant_id,
            job_id=job_id,
            target_state=DiscoveryJobStatus.FAILED,
            failure_code=failure_code,
            failure_message=failure_message,
        )


class DiscoveryEvidenceRepository:
    """Tenant-scoped append-only repository for discovery evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        evidence: DiscoveryEvidence,
        *,
        collector_version: str | None = None,
    ) -> DiscoveryEvidenceRecord:
        job = self.session.get(DiscoveryJobRecord, evidence.traceability.job_id)
        target = self.session.get(
            DiscoveryTargetRecord, evidence.traceability.target_id
        )
        run = self.session.get(
            DiscoveryRunRecord, evidence.traceability.discovery_run_id
        )
        tenant_id = evidence.traceability.tenant_id
        if job is None or job.tenant_id != tenant_id:
            raise DiscoveryResourceNotFoundError("Discovery job was not found.")
        if target is None or target.tenant_id != tenant_id:
            raise DiscoveryResourceNotFoundError("Discovery target was not found.")
        if run is None or run.tenant_id not in {None, tenant_id}:
            raise DiscoveryResourceNotFoundError("Discovery run was not found.")
        if job.target_id != target.id or job.run_id != run.id:
            raise DiscoveryPersistenceError(
                "Evidence relationships do not match the discovery job."
            )
        payload_hash = _payload_hash(evidence.payload)
        if payload_hash != evidence.content_hash:
            raise DiscoveryPersistenceError("Evidence payload hash does not match.")
        record = DiscoveryEvidenceRecord(
            id=evidence.id,
            tenant_id=evidence.traceability.tenant_id,
            job_id=evidence.traceability.job_id,
            target_id=evidence.traceability.target_id,
            run_id=evidence.traceability.discovery_run_id,
            evidence_type=evidence.evidence_type,
            source=evidence.collector_name,
            observed_at=evidence.captured_at,
            payload=dict(evidence.payload),
            payload_hash=payload_hash,
            collector=evidence.collector_name,
            collector_version=collector_version,
            command_or_probe=evidence.command_or_probe,
            sequence=evidence.sequence,
            parser_version=evidence.parser_version,
            normalization_version=evidence.normalization_version,
        )
        self.session.add(record)
        return record

    def get(
        self, *, tenant_id: str, evidence_id: UUID
    ) -> DiscoveryEvidenceRecord | None:
        statement = select(DiscoveryEvidenceRecord).where(
            DiscoveryEvidenceRecord.id == evidence_id,
            DiscoveryEvidenceRecord.tenant_id == tenant_id,
        )
        return self.session.scalars(statement).first()

    def list_for_job(
        self, *, tenant_id: str, job_id: UUID
    ) -> tuple[DiscoveryEvidenceRecord, ...]:
        statement = (
            select(DiscoveryEvidenceRecord)
            .where(
                DiscoveryEvidenceRecord.tenant_id == tenant_id,
                DiscoveryEvidenceRecord.job_id == job_id,
            )
            .order_by(DiscoveryEvidenceRecord.sequence.asc())
        )
        return tuple(self.session.scalars(statement).all())


__all__ = [
    "DiscoveryEvidenceRepository",
    "DiscoveryJobRepository",
    "DiscoveryPersistenceError",
    "DiscoveryResourceNotFoundError",
    "DiscoveryTargetRepository",
    "DuplicateActiveDiscoveryError",
    "InvalidDiscoveryTransitionError",
]
