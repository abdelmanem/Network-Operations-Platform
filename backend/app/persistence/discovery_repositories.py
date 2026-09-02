"""Repositories for the M31 discovery persistence boundary."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import String, cast as sql_cast, delete, func, or_, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from backend.app.discovery.contracts import (
    DiscoveryEvidence,
    DiscoveryFailureCode,
    DiscoveryJobStatus,
    transition_job,
)
from backend.app.discovery.leases import (
    DISCOVERY_JOB_LEASE_SECONDS,
    HEARTBEAT_LOST_MESSAGE,
    LEASE_EXPIRED_MESSAGE,
    PROTECTED_DISCOVERY_JOB_ID,
)
from backend.app.persistence.models import (
    CredentialProfileRecord,
    DiscoveryDeviceResultRecord,
    DiscoveryEvidenceRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
    DiscoveryTransportAttemptRecord,
)


class DiscoveryPersistenceError(RuntimeError):
    """Base error for discovery persistence operations."""


class DuplicateActiveDiscoveryError(DiscoveryPersistenceError):
    """Raised when a target already has an active discovery job."""


class DiscoveryResourceNotFoundError(DiscoveryPersistenceError):
    """Raised when a tenant-scoped discovery resource is unavailable."""


class InvalidDiscoveryTransitionError(DiscoveryPersistenceError):
    """Raised when a job transition violates the M31 state machine."""


class DiscoveryCancellationConflictError(DiscoveryPersistenceError):
    """Raised when a terminal discovery job cannot be cancelled."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


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
        scope_type: str = "single_device",
        scope_end: str | None = None,
        scope_cidr: str | None = None,
        credential_reference: str,
        credential_profile_id: str | None = None,
        credential_references: Mapping[str, object] | None = None,
        allowed_fallback_transports: list[str] | None = None,
        allow_insecure_telnet: bool = False,
        allow_insecure_http: bool = False,
        vendor: str | None = None,
        hostname: str | None = None,
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
            scope_type=scope_type,
            scope_end=scope_end,
            scope_cidr=scope_cidr,
            vendor=vendor,
            hostname=hostname,
            platform_hint=platform_hint,
            preferred_transport=preferred_transport,
            enabled=enabled,
            credential_reference=credential_reference,
            credential_profile_id=credential_profile_id,
            credential_references=(
                {} if credential_references is None else dict(credential_references)
            ),
            allowed_fallback_transports=(
                []
                if allowed_fallback_transports is None
                else list(allowed_fallback_transports)
            ),
            allow_insecure_telnet=bool(allow_insecure_telnet),
            allow_insecure_http=bool(allow_insecure_http),
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

    def update(
        self,
        *,
        tenant_id: str,
        target_id: UUID,
        **changes: Any,
    ) -> DiscoveryTargetRecord:
        record = self.get(tenant_id=tenant_id, target_id=target_id)
        if record is None:
            raise DiscoveryResourceNotFoundError("Discovery target was not found.")
        for key, value in changes.items():
            setattr(record, key, value)
        self.session.flush()
        return record

    def delete(self, *, tenant_id: str, target_id: UUID) -> bool:
        record = self.get(tenant_id=tenant_id, target_id=target_id)
        if record is None:
            return False

        job_ids = tuple(
            row
            for row in self.session.scalars(
                select(DiscoveryJobRecord.id).where(
                    DiscoveryJobRecord.tenant_id == tenant_id,
                    DiscoveryJobRecord.target_id == target_id,
                )
            )
        )
        if job_ids:
            device_result_ids = tuple(
                row
                for row in self.session.scalars(
                    select(DiscoveryDeviceResultRecord.id).where(
                        or_(
                            DiscoveryDeviceResultRecord.discovery_job_id.in_(job_ids),
                            DiscoveryDeviceResultRecord.child_job_id.in_(job_ids),
                        )
                    )
                )
            )
            if device_result_ids:
                self.session.execute(
                    delete(DiscoveryTransportAttemptRecord).where(
                        DiscoveryTransportAttemptRecord.device_result_id.in_(device_result_ids)
                    )
                )
                self.session.execute(
                    delete(DiscoveryDeviceResultRecord).where(
                        DiscoveryDeviceResultRecord.id.in_(device_result_ids)
                    )
                )
            self.session.execute(
                delete(DiscoveryEvidenceRecord).where(
                    or_(
                        DiscoveryEvidenceRecord.target_id == target_id,
                        DiscoveryEvidenceRecord.job_id.in_(job_ids),
                    )
                )
            )
            self.session.execute(
                delete(DiscoveryJobRecord).where(DiscoveryJobRecord.id.in_(job_ids))
            )
        else:
            self.session.execute(
                delete(DiscoveryEvidenceRecord).where(
                    DiscoveryEvidenceRecord.target_id == target_id
                )
            )

        self.session.delete(record)
        self.session.flush()
        return True


class CredentialProfileRepository:
    """Tenant-scoped repository for secret-free credential profile metadata."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        tenant_id: str,
        name: str,
        provider_reference: str,
        transport_types: list[str],
        description: str | None = None,
        vendor: str | None = None,
        platform: str | None = None,
        credential_type: str | None = None,
        username: str | None = None,
    ) -> CredentialProfileRecord:
        record = CredentialProfileRecord(
            tenant_id=tenant_id,
            name=name,
            provider_reference=provider_reference,
            transport_types=list(transport_types),
            description=description,
            vendor=vendor,
            platform=platform,
            credential_type=credential_type,
            username=username,
            secret_status="configured",
            enabled=True,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get(
        self, *, tenant_id: str, profile_id: UUID
    ) -> CredentialProfileRecord | None:
        statement = select(CredentialProfileRecord).where(
            CredentialProfileRecord.id == profile_id,
            CredentialProfileRecord.tenant_id == tenant_id,
        )
        return self.session.scalars(statement).first()

    def update(
        self,
        *,
        tenant_id: str,
        profile_id: UUID,
        **changes: Any,
    ) -> CredentialProfileRecord:
        record = self.get(tenant_id=tenant_id, profile_id=profile_id)
        if record is None:
            raise DiscoveryResourceNotFoundError("Credential profile was not found.")
        for key, value in changes.items():
            setattr(record, key, value)
        self.session.flush()
        return record

    def delete(self, *, tenant_id: str, profile_id: UUID) -> bool:
        record = self.get(tenant_id=tenant_id, profile_id=profile_id)
        if record is None:
            return False
        self.session.delete(record)
        self.session.flush()
        return True

    def list(self, *, tenant_id: str) -> tuple[CredentialProfileRecord, ...]:
        statement = (
            select(CredentialProfileRecord)
            .where(
                CredentialProfileRecord.tenant_id == tenant_id,
                CredentialProfileRecord.enabled.is_(True),
            )
            .order_by(CredentialProfileRecord.name.asc())
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
        parent_job_id: UUID | None = None,
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
            parent_job_id=parent_job_id,
            state=DiscoveryJobStatus.QUEUED.value,
            created_by=created_by,
            requested_capabilities=(
                {} if requested_capabilities is None else dict(requested_capabilities)
            ),
            timeout_seconds=timeout_seconds,
            correlation_id=correlation_id,
            execution_owner=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
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
        statement = (
            select(DiscoveryJobRecord)
            .where(
                DiscoveryJobRecord.id == job_id,
                DiscoveryJobRecord.tenant_id == tenant_id,
            )
            .execution_options(populate_existing=True)
        )
        return self.session.scalars(statement).first()

    def list_queued_roots(self, *, limit: int) -> tuple[tuple[str, UUID], ...]:
        """Return durable root jobs eligible for an atomic worker claim."""

        statement = (
            select(DiscoveryJobRecord.tenant_id, DiscoveryJobRecord.id)
            .where(
                DiscoveryJobRecord.state == DiscoveryJobStatus.QUEUED.value,
                DiscoveryJobRecord.parent_job_id.is_(None),
                DiscoveryJobRecord.id != PROTECTED_DISCOVERY_JOB_ID,
                DiscoveryJobRecord.execution_owner.is_(None),
                DiscoveryJobRecord.lease_expires_at.is_(None),
                DiscoveryJobRecord.last_heartbeat_at.is_(None),
            )
            .order_by(DiscoveryJobRecord.requested_at.asc())
            .limit(limit)
        )
        return tuple((tenant_id, job_id) for tenant_id, job_id in self.session.execute(statement))

    def list(self, *, tenant_id: str) -> tuple[DiscoveryJobRecord, ...]:
        statement = (
            select(DiscoveryJobRecord)
            .where(DiscoveryJobRecord.tenant_id == tenant_id)
            .order_by(DiscoveryJobRecord.requested_at.desc())
        )
        return tuple(self.session.scalars(statement).all())

    def list_page(
        self,
        *,
        tenant_id: str,
        page: int = 1,
        page_size: int = 25,
        q: str | None = None,
        status: str | None = None,
        target_id: UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort: str | None = None,
        order: str | None = None,
    ) -> tuple[tuple[DiscoveryJobRecord, ...], int]:
        """Return one filtered/sorted page and the tenant-scoped total."""

        filters = [DiscoveryJobRecord.tenant_id == tenant_id]

        if status and status.strip().lower() not in {"", "all"}:
            filters.append(DiscoveryJobRecord.state == status.strip().lower())

        if target_id is not None:
            filters.append(DiscoveryJobRecord.target_id == target_id)

        if date_from is not None:
            filters.append(DiscoveryJobRecord.requested_at >= date_from)

        if date_to is not None:
            filters.append(DiscoveryJobRecord.requested_at <= date_to)

        if q and q.strip():
            clean_q = q.strip()
            term = f"%{clean_q}%"
            q_conditions = [
                sql_cast(DiscoveryJobRecord.id, String).ilike(term),
                sql_cast(DiscoveryJobRecord.run_id, String).ilike(term),
                sql_cast(DiscoveryJobRecord.target_id, String).ilike(term),
                sql_cast(DiscoveryJobRecord.execution_owner, String).ilike(term),
                DiscoveryJobRecord.failure_code.ilike(term),
                DiscoveryJobRecord.failure_message.ilike(term),
                DiscoveryJobRecord.state.ilike(term),
                DiscoveryTargetRecord.identifier.ilike(term),
                DiscoveryTargetRecord.address.ilike(term),
            ]
            filters.append(or_(*q_conditions))

        normalized_sort = (sort or "newest").strip().lower()
        normalized_order = (order or "").strip().lower()

        bind = self.session.get_bind()
        is_sqlite = bind.dialect.name == "sqlite"
        order_clause: ColumnElement[Any]

        if normalized_sort in {"newest", "requested_at", "created_at"}:
            direction = normalized_order or "desc"
            order_clause = (
                DiscoveryJobRecord.requested_at.asc()
                if direction == "asc"
                else DiscoveryJobRecord.requested_at.desc()
            )
        elif normalized_sort in {"oldest"}:
            order_clause = DiscoveryJobRecord.requested_at.asc()
        elif normalized_sort in {"started_at", "recently_started"}:
            direction = normalized_order or "desc"
            col = (
                DiscoveryJobRecord.started_at.asc()
                if direction == "asc"
                else DiscoveryJobRecord.started_at.desc()
            )
            order_clause = col.nulls_last()
        elif normalized_sort in {"completed_at", "finished_at", "recently_completed"}:
            direction = normalized_order or "desc"
            col = (
                DiscoveryJobRecord.completed_at.asc()
                if direction == "asc"
                else DiscoveryJobRecord.completed_at.desc()
            )
            order_clause = col.nulls_last()
        elif normalized_sort in {"duration", "longest_running"}:
            direction = normalized_order or "desc"
            if is_sqlite:
                now_expr = func.datetime("now")
                duration_expr = (
                    func.julianday(
                        func.coalesce(DiscoveryJobRecord.completed_at, now_expr)
                    )
                    - func.julianday(DiscoveryJobRecord.started_at)
                )
            else:
                duration_expr = (
                    func.coalesce(DiscoveryJobRecord.completed_at, func.now())
                    - DiscoveryJobRecord.started_at
                )
            col = duration_expr.asc() if direction == "asc" else duration_expr.desc()
            order_clause = col.nulls_last()
        elif normalized_sort in {"target", "target_identifier", "target_name"}:
            direction = normalized_order or "asc"
            order_clause = (
                DiscoveryTargetRecord.identifier.asc()
                if direction == "asc"
                else DiscoveryTargetRecord.identifier.desc()
            )
        elif normalized_sort in {"status", "state"}:
            direction = normalized_order or "asc"
            order_clause = (
                DiscoveryJobRecord.state.asc()
                if direction == "asc"
                else DiscoveryJobRecord.state.desc()
            )
        else:
            raise ValueError(f"Unsupported sort field: {sort}")

        count_stmt = (
            select(func.count())
            .select_from(DiscoveryJobRecord)
            .outerjoin(
                DiscoveryTargetRecord,
                DiscoveryJobRecord.target_id == DiscoveryTargetRecord.id,
            )
            .where(*filters)
        )
        total = self.session.scalar(count_stmt) or 0

        select_stmt = (
            select(DiscoveryJobRecord)
            .outerjoin(
                DiscoveryTargetRecord,
                DiscoveryJobRecord.target_id == DiscoveryTargetRecord.id,
            )
            .where(*filters)
            .order_by(order_clause)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return tuple(self.session.scalars(select_stmt).all()), int(total)

    def claim(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        execution_owner: UUID | None = None,
        lease_seconds: float = DISCOVERY_JOB_LEASE_SECONDS,
    ) -> DiscoveryJobRecord:
        """Atomically transition one queued job to a leased running owner."""

        if job_id == PROTECTED_DISCOVERY_JOB_ID:
            raise InvalidDiscoveryTransitionError(
                "Protected discovery job cannot be claimed."
            )
        if lease_seconds <= 0:
            raise InvalidDiscoveryTransitionError("A positive lease is required.")
        owner = execution_owner or uuid4()
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
                    DiscoveryJobRecord.execution_owner.is_(None),
                    DiscoveryJobRecord.lease_expires_at.is_(None),
                    DiscoveryJobRecord.last_heartbeat_at.is_(None),
                )
                .values(
                    state=DiscoveryJobStatus.RUNNING.value,
                    started_at=now,
                    updated_at=now,
                    attempts=DiscoveryJobRecord.attempts + 1,
                    execution_owner=owner,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    last_heartbeat_at=now,
                )
                .returning(DiscoveryJobRecord.id)
            ),
        )
        if result.scalar_one_or_none() is None:
            self.session.rollback()
            raise InvalidDiscoveryTransitionError(
                "Only queued discovery jobs can be claimed."
            )
        self.session.flush()
        return self.get(tenant_id=tenant_id, job_id=job_id)  # type: ignore[return-value]

    def renew_lease(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        execution_owner: UUID,
        lease_seconds: float,
    ) -> bool:
        """Renew a worker-owned root job and its active fan-out children."""

        now = _utc_now()
        result = self.session.execute(
            update(DiscoveryJobRecord)
            .where(
                DiscoveryJobRecord.tenant_id == tenant_id,
                DiscoveryJobRecord.execution_owner == execution_owner,
                DiscoveryJobRecord.state == DiscoveryJobStatus.RUNNING.value,
                (DiscoveryJobRecord.id == job_id)
                | (DiscoveryJobRecord.parent_job_id == job_id),
            )
            .values(
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                last_heartbeat_at=now,
                updated_at=now,
            )
            .returning(DiscoveryJobRecord.id)
        )
        if result.first() is None:
            self.session.rollback()
            return False
        self.session.flush()
        return True

    def owned_running_job(
        self, *, tenant_id: str, job_id: UUID, execution_owner: UUID
    ) -> DiscoveryJobRecord | None:
        statement = select(DiscoveryJobRecord).where(
            DiscoveryJobRecord.id == job_id,
            DiscoveryJobRecord.tenant_id == tenant_id,
            DiscoveryJobRecord.state == DiscoveryJobStatus.RUNNING.value,
            DiscoveryJobRecord.execution_owner == execution_owner,
        )
        return self.session.scalars(statement).first()

    def transition(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        target_state: DiscoveryJobStatus,
        failure_code: str | None = None,
        failure_message: str | None = None,
        require_no_cancellation: bool = False,
        expected_execution_owner: UUID | None = None,
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
        statement = update(DiscoveryJobRecord).where(
            DiscoveryJobRecord.id == job_id,
            DiscoveryJobRecord.tenant_id == tenant_id,
            DiscoveryJobRecord.state == job.state,
        )
        if require_no_cancellation:
            statement = statement.where(
                DiscoveryJobRecord.cancellation_requested_at.is_(None)
            )
        if expected_execution_owner is not None:
            statement = statement.where(
                DiscoveryJobRecord.execution_owner == expected_execution_owner
            )
        if target_state.is_terminal:
            values.update(
                execution_owner=None,
                lease_expires_at=None,
                last_heartbeat_at=None,
            )
        result = self.session.execute(
            statement.values(**values).returning(DiscoveryJobRecord.id)
        )
        if result.scalar_one_or_none() is None:
            self.session.rollback()
            raise InvalidDiscoveryTransitionError(
                "Discovery job changed state before transition could be applied."
            )
        self.session.flush()
        return self.get(tenant_id=tenant_id, job_id=job_id)  # type: ignore[return-value]

    def request_cancellation(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        requested_by: UUID,
        reason: str,
    ) -> tuple[DiscoveryJobRecord, bool]:
        """Persist a cancellation request, atomically cancelling queued work."""

        job = self.get(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            raise DiscoveryResourceNotFoundError("Discovery job was not found.")
        if DiscoveryJobStatus(job.state).is_terminal:
            if job.state == DiscoveryJobStatus.CANCELLED.value:
                return job, False
            raise DiscoveryCancellationConflictError(
                f"Discovery job is already {job.state}."
            )
        if job.cancellation_requested_at is not None:
            return job, False

        now = _utc_now()
        values: dict[str, object] = {
            "cancellation_requested_at": now,
            "cancellation_requested_by": requested_by,
            "cancellation_reason": reason,
            "updated_at": now,
        }
        if job.state == DiscoveryJobStatus.QUEUED.value:
            values.update(
                state=DiscoveryJobStatus.CANCELLED.value,
                completed_at=now,
                failure_code=DiscoveryFailureCode.CANCELLED.value,
                failure_message=reason,
                execution_owner=None,
                lease_expires_at=None,
                last_heartbeat_at=None,
            )
        statement = update(DiscoveryJobRecord).where(
            DiscoveryJobRecord.id == job_id,
            DiscoveryJobRecord.tenant_id == tenant_id,
            DiscoveryJobRecord.state == job.state,
        )
        result = self.session.execute(
            statement.values(**values).returning(DiscoveryJobRecord.id)
        )
        if result.scalar_one_or_none() is None:
            self.session.rollback()
            current = self.get(tenant_id=tenant_id, job_id=job_id)
            if (
                current is not None
                and current.state == DiscoveryJobStatus.CANCELLED.value
            ):
                return current, False
            raise DiscoveryCancellationConflictError(
                "Discovery job changed state before cancellation could be applied."
            )
        self.session.flush()
        return self.get(tenant_id=tenant_id, job_id=job_id), True  # type: ignore[return-value]

    def cancellation_requested(self, *, tenant_id: str, job_id: UUID) -> bool:
        """Read cancellation state directly, bypassing the ORM identity map."""

        value = self.session.scalar(
            select(DiscoveryJobRecord.cancellation_requested_at).where(
                DiscoveryJobRecord.id == job_id,
                DiscoveryJobRecord.tenant_id == tenant_id,
            )
        )
        if value is not None:
            return True
        state = self.session.scalar(
            select(DiscoveryJobRecord.state).where(
                DiscoveryJobRecord.id == job_id,
                DiscoveryJobRecord.tenant_id == tenant_id,
            )
        )
        return state == DiscoveryJobStatus.CANCELLED.value

    def finalise_cancellation(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        expected_execution_owner: UUID | None = None,
    ) -> DiscoveryJobRecord:
        job = self.get(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            raise DiscoveryResourceNotFoundError("Discovery job was not found.")
        if job.state == DiscoveryJobStatus.CANCELLED.value:
            return job
        if job.cancellation_requested_at is None:
            raise InvalidDiscoveryTransitionError("Cancellation was not requested.")
        return self.transition(
            tenant_id=tenant_id,
            job_id=job_id,
            target_state=DiscoveryJobStatus.CANCELLED,
            failure_code=DiscoveryFailureCode.CANCELLED.value,
            failure_message=job.cancellation_reason or "Cancelled by operator.",
            expected_execution_owner=expected_execution_owner,
        )

    def resolve_stale_cancellation(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
    ) -> DiscoveryJobRecord:
        """Resolve a job with cancellation requested and no active execution lease.

        Atomically transitions the running job to cancelled state, clears
        ownership and lease tracking fields, and sets finished/completion time,
        while preserving all cancellation request metadata, evidence, and results.
        Rejects with conflict if the job is actively executing with a valid lease.
        """
        job = self.get(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            raise DiscoveryResourceNotFoundError("Discovery job was not found.")

        if job.state == DiscoveryJobStatus.CANCELLED.value:
            return job

        if DiscoveryJobStatus(job.state).is_terminal:
            raise DiscoveryCancellationConflictError(
                f"Discovery job is already in terminal state '{job.state}'."
            )

        if job.state != DiscoveryJobStatus.RUNNING.value:
            raise DiscoveryCancellationConflictError(
                f"Cannot force resolve job in '{job.state}' state; use standard cancellation."
            )

        if job.cancellation_requested_at is None:
            raise DiscoveryCancellationConflictError(
                "Cancellation was not requested for this discovery job."
            )

        now = _utc_now()
        lease_expires_at = _as_utc(job.lease_expires_at)

        # Verify whether there is a valid active lease held by a worker
        if (
            job.execution_owner is not None
            and lease_expires_at is not None
            and lease_expires_at > now
        ):
            raise DiscoveryCancellationConflictError(
                "Cannot resolve cancellation for an actively executing job with a valid worker lease."
            )

        statement = (
            update(DiscoveryJobRecord)
            .where(
                DiscoveryJobRecord.id == job_id,
                DiscoveryJobRecord.tenant_id == tenant_id,
                DiscoveryJobRecord.state == DiscoveryJobStatus.RUNNING.value,
                DiscoveryJobRecord.cancellation_requested_at.is_not(None),
                or_(
                    DiscoveryJobRecord.execution_owner.is_(None),
                    DiscoveryJobRecord.lease_expires_at.is_(None),
                    DiscoveryJobRecord.lease_expires_at <= now,
                ),
            )
            .values(
                state=DiscoveryJobStatus.CANCELLED.value,
                failure_code=DiscoveryFailureCode.CANCELLED.value,
                failure_message=job.cancellation_reason or "Cancelled by operator.",
                completed_at=now,
                execution_owner=None,
                lease_expires_at=None,
                last_heartbeat_at=None,
                updated_at=now,
            )
        )
        result = self.session.execute(
            statement.returning(DiscoveryJobRecord.id).execution_options(
                synchronize_session="fetch"
            )
        )
        if result.scalar_one_or_none() is None:
            self.session.rollback()
            current = self.get(tenant_id=tenant_id, job_id=job_id)
            if current is not None and current.state == DiscoveryJobStatus.CANCELLED.value:
                return current
            current_lease_expires_at = (
                _as_utc(current.lease_expires_at) if current is not None else None
            )
            if (
                current is not None
                and current.execution_owner is not None
                and current_lease_expires_at is not None
                and current_lease_expires_at > now
            ):
                raise DiscoveryCancellationConflictError(
                    "Cannot resolve cancellation for an actively executing job with a valid worker lease."
                )
            raise DiscoveryCancellationConflictError(
                "Discovery job state changed before cancellation could be resolved."
            )

        # Reconcile child jobs if this was a parent job
        child_ids = list(
            self.session.scalars(
                select(DiscoveryJobRecord.id).where(
                    DiscoveryJobRecord.tenant_id == tenant_id,
                    DiscoveryJobRecord.parent_job_id == job_id,
                    DiscoveryJobRecord.state == DiscoveryJobStatus.RUNNING.value,
                )
            )
        )
        if child_ids:
            self.session.execute(
                update(DiscoveryJobRecord)
                .where(
                    DiscoveryJobRecord.id.in_(child_ids),
                    DiscoveryJobRecord.tenant_id == tenant_id,
                    DiscoveryJobRecord.state == DiscoveryJobStatus.RUNNING.value,
                )
                .values(
                    state=DiscoveryJobStatus.CANCELLED.value,
                    failure_code=DiscoveryFailureCode.CANCELLED.value,
                    failure_message=job.cancellation_reason or "Cancelled by operator.",
                    completed_at=now,
                    execution_owner=None,
                    lease_expires_at=None,
                    last_heartbeat_at=None,
                    updated_at=now,
                )
            )

        self.session.flush()
        return self.get(tenant_id=tenant_id, job_id=job_id)  # type: ignore[return-value]

    def recover_expired_owned_jobs(
        self,
        *,
        stale_before: datetime,
    ) -> tuple[tuple[str, UUID], ...]:
        """Return expired leased root jobs that are safe to reconcile.

        Cross-tenant discovery is intentional. Callers must still recover each
        job with an explicit tenant_id. Unowned running jobs and the protected
        job id are never returned.
        """

        statement = select(DiscoveryJobRecord.tenant_id, DiscoveryJobRecord.id).where(
            DiscoveryJobRecord.state == DiscoveryJobStatus.RUNNING.value,
            DiscoveryJobRecord.parent_job_id.is_(None),
            DiscoveryJobRecord.id != PROTECTED_DISCOVERY_JOB_ID,
            DiscoveryJobRecord.execution_owner.is_not(None),
            DiscoveryJobRecord.lease_expires_at.is_not(None),
            DiscoveryJobRecord.last_heartbeat_at.is_not(None),
            DiscoveryJobRecord.lease_expires_at < stale_before,
        )
        return tuple(
            (tenant_id, job_id) for tenant_id, job_id in self.session.execute(statement)
        )

    def recover_expired_owned_job(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        stale_before: datetime,
    ) -> DiscoveryJobRecord | None:
        """Terminally reconcile one expired lease without re-running network work."""

        if job_id == PROTECTED_DISCOVERY_JOB_ID:
            return None
        job = self.get(tenant_id=tenant_id, job_id=job_id)
        if (
            job is None
            or job.state != DiscoveryJobStatus.RUNNING.value
            or job.execution_owner is None
            or job.lease_expires_at is None
            or job.last_heartbeat_at is None
            or (_as_utc(job.lease_expires_at) or _utc_now()) >= (_as_utc(stale_before) or _utc_now())
        ):
            return None
        return self._reconcile_owned_tree(
            tenant_id=tenant_id,
            job_id=job_id,
            execution_owner=job.execution_owner,
            failure_message=LEASE_EXPIRED_MESSAGE,
        )

    def abandon_owned_job(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        execution_owner: UUID,
        failure_message: str = HEARTBEAT_LOST_MESSAGE,
    ) -> DiscoveryJobRecord | None:
        """Stop an owned running tree at a cooperative boundary.

        Used when a live worker loses its heartbeat so a second worker cannot
        recover a job that may still be executing.
        """

        if job_id == PROTECTED_DISCOVERY_JOB_ID:
            return None
        job = self.owned_running_job(
            tenant_id=tenant_id, job_id=job_id, execution_owner=execution_owner
        )
        if job is None:
            return None
        return self._reconcile_owned_tree(
            tenant_id=tenant_id,
            job_id=job_id,
            execution_owner=execution_owner,
            failure_message=failure_message,
        )

    def _reconcile_owned_tree(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        execution_owner: UUID,
        failure_message: str,
    ) -> DiscoveryJobRecord | None:
        job = self.get(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            return None
        cancel = self.cancellation_requested(tenant_id=tenant_id, job_id=job_id)
        target_state = (
            DiscoveryJobStatus.CANCELLED if cancel else DiscoveryJobStatus.FAILED
        )
        failure_code = (
            DiscoveryFailureCode.CANCELLED.value
            if cancel
            else DiscoveryFailureCode.DISCOVERY_FAILED.value
        )
        message = (
            job.cancellation_reason or "Cancelled by operator."
            if cancel
            else failure_message
        )
        children = self.session.scalars(
            select(DiscoveryJobRecord).where(
                DiscoveryJobRecord.tenant_id == tenant_id,
                DiscoveryJobRecord.parent_job_id == job_id,
                DiscoveryJobRecord.state.in_(
                    (
                        DiscoveryJobStatus.QUEUED.value,
                        DiscoveryJobStatus.RUNNING.value,
                    )
                ),
            )
        ).all()
        for child in children:
            if child.state == DiscoveryJobStatus.QUEUED.value:
                self.transition(
                    tenant_id=tenant_id,
                    job_id=child.id,
                    target_state=target_state,
                    failure_code=failure_code,
                    failure_message=message,
                )
                continue
            if child.execution_owner != execution_owner:
                continue
            self.transition(
                tenant_id=tenant_id,
                job_id=child.id,
                target_state=target_state,
                failure_code=failure_code,
                failure_message=message,
                expected_execution_owner=execution_owner,
            )
        return self.transition(
            tenant_id=tenant_id,
            job_id=job_id,
            target_state=target_state,
            failure_code=failure_code,
            failure_message=message,
            expected_execution_owner=execution_owner,
        )

    def record_selection(
        self,
        *,
        tenant_id: str,
        job_id: UUID,
        selected_transport: str | None,
        selected_platform: str | None,
    ) -> DiscoveryJobRecord:
        """Persist execution selection metadata while a job is running."""

        job = self.get(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            raise DiscoveryResourceNotFoundError("Discovery job was not found.")
        if job.state != DiscoveryJobStatus.RUNNING.value:
            raise InvalidDiscoveryTransitionError(
                "Selection metadata requires a running discovery job."
            )
        self.session.execute(
            update(DiscoveryJobRecord)
            .where(
                DiscoveryJobRecord.id == job_id,
                DiscoveryJobRecord.tenant_id == tenant_id,
            )
            .values(
                selected_transport=selected_transport,
                selected_platform=selected_platform,
                updated_at=_utc_now(),
            )
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
        expected_execution_owner: UUID | None = None,
    ) -> DiscoveryJobRecord:
        """Rollback pending work, then persist failure in a clean transaction."""

        self.session.rollback()
        return self.transition(
            tenant_id=tenant_id,
            job_id=job_id,
            target_state=DiscoveryJobStatus.FAILED,
            failure_code=failure_code,
            failure_message=failure_message,
            require_no_cancellation=True,
            expected_execution_owner=expected_execution_owner,
        )


class DiscoveryTransportAttemptRepository:
    """Persist secret-free transport attempt history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def start(
        self,
        *,
        tenant_id: str,
        device_result_id: UUID,
        transport: str,
        attempt_order: int,
        correlation_id: str | None = None,
    ) -> DiscoveryTransportAttemptRecord:
        record = DiscoveryTransportAttemptRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            device_result_id=device_result_id,
            transport=transport,
            attempt_order=attempt_order,
            result="running",
            started_at=_utc_now(),
            correlation_id=correlation_id,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def finish(
        self,
        record: DiscoveryTransportAttemptRecord,
        *,
        result: str,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> DiscoveryTransportAttemptRecord:
        completed_at = _utc_now()
        record.result = result
        record.failure_code = failure_code
        record.failure_message = failure_message
        record.completed_at = completed_at
        started_at = record.started_at
        if started_at is not None and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        record.duration_ms = max(
            0,
            int(
                (
                    completed_at - (started_at or completed_at)
                ).total_seconds()
                * 1000
            ),
        )
        self.session.flush()
        return record


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
    "CredentialProfileRepository",
    "DiscoveryEvidenceRepository",
    "DiscoveryCancellationConflictError",
    "DiscoveryJobRepository",
    "DiscoveryPersistenceError",
    "DiscoveryResourceNotFoundError",
    "DiscoveryTargetRepository",
    "DuplicateActiveDiscoveryError",
    "InvalidDiscoveryTransitionError",
]
