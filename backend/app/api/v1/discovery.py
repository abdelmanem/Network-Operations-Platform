"""M31.4 discovery API boundary."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_application_container, get_db_session
from backend.app.audit.api.router import get_audit_service
from backend.app.audit.application.services import AuditService
from backend.app.auth.api.dependencies import require_permission
from backend.app.auth.domain.models import User
from backend.app.collectors.registry import CollectorRegistry
from backend.app.database.session import SessionLocal
from backend.app.discovery.contracts import DiscoveryJobStatus
from backend.app.discovery.execution import DiscoveryExecutionService
from backend.app.discovery.fanout import DiscoveryFanoutService
from backend.app.normalization.engine import NormalizationEngine
from backend.app.parsers.pipeline import ParserPipeline
from backend.app.persistence.discovery_repositories import (
    CredentialProfileRepository,
    DiscoveryCancellationConflictError,
    DiscoveryEvidenceRepository,
    DiscoveryJobRepository,
    DiscoveryPersistenceError,
    DiscoveryResourceNotFoundError,
    DiscoveryTargetRepository,
    InvalidDiscoveryTransitionError,
)
from backend.app.persistence.models import (
    DiscoveryDeviceResultRecord,
    DiscoveryEvidenceRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
    DiscoveryTransportAttemptRecord,
    SnapshotDeviceRecord,
    SnapshotRecord,
)
from backend.app.schemas.discovery import (
    CredentialProfileRequest,
    CredentialProfileResponse,
    DiscoveryDeviceResultResponse,
    DiscoveryEvidenceResponse,
    DiscoveryJobCancellationRequest,
    DiscoveryJobListResponse,
    DiscoveryJobRequest,
    DiscoveryJobResponse,
    DiscoveryTargetRequest,
    DiscoveryTargetResponse,
    DiscoveryTargetUpdateRequest,
    DiscoveryTransportAttemptResponse,
)

if TYPE_CHECKING:
    from backend.app.core.application import ApplicationContainer

router: APIRouter = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post(
    "/targets",
    response_model=DiscoveryTargetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a discovery target",
)
def create_target(
    payload: DiscoveryTargetRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[User, Depends(require_permission("discovery:target:write"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> DiscoveryTargetResponse:
    _validate_tenant(payload.tenant_id, tenant_id)
    try:
        record = DiscoveryTargetRepository(db_session).create(
            tenant_id=tenant_id,
            identifier=payload.identifier,
            address=payload.address or payload.scope_cidr or "",
            scope_type=payload.scope_type.value,
            scope_end=payload.scope_end,
            scope_cidr=payload.scope_cidr,
            hostname=payload.hostname,
            vendor=payload.vendor,
            credential_reference=(
                payload.credential_profile_id or payload.credential_reference or ""
            ),
            credential_profile_id=payload.credential_profile_id,
            credential_references=dict(payload.credential_references),
            allowed_fallback_transports=payload.allowed_fallback_transports,
            platform_hint=payload.platform_hint,
            preferred_transport=payload.preferred_transport,
            enabled=payload.enabled,
            metadata=payload.metadata,
            created_by=user.id,
        )
        db_session.commit()
    except DiscoveryPersistenceError as exc:
        db_session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _target_response(record)


@router.get(
    "/targets",
    response_model=list[DiscoveryTargetResponse],
    summary="List discovery targets",
)
def list_targets(
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:target:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> list[DiscoveryTargetResponse]:
    return [
        _target_response(record)
        for record in DiscoveryTargetRepository(db_session).list(tenant_id=tenant_id)
    ]


@router.patch(
    "/targets/{target_id}",
    response_model=DiscoveryTargetResponse,
    summary="Update a discovery target",
)
def update_target(
    target_id: UUID,
    payload: DiscoveryTargetUpdateRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:target:write"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> DiscoveryTargetResponse:
    target_repo = DiscoveryTargetRepository(db_session)
    existing_target = target_repo.get(tenant_id=tenant_id, target_id=target_id)
    if existing_target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discovery target was not found.",
        )

    changes: dict[str, Any] = {}
    if payload.enabled is not None:
        changes["enabled"] = payload.enabled
    if payload.platform_hint is not None:
        changes["platform_hint"] = payload.platform_hint
    if payload.preferred_transport is not None:
        changes["preferred_transport"] = payload.preferred_transport

    if payload.credential_profile_id is not None:
        try:
            profile_uuid = UUID(payload.credential_profile_id)
        except ValueError:
            profile_uuid = None

        profile = None
        if profile_uuid is not None:
            profile = CredentialProfileRepository(db_session).get(
                tenant_id=tenant_id,
                profile_id=profile_uuid,
            )
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential profile was not found.",
            )

        effective_transport = (
            payload.preferred_transport
            or existing_target.preferred_transport
            or "ssh"
        )
        normalized_transport = effective_transport.lower()
        if normalized_transport in {"netmiko", "paramiko"}:
            normalized_transport = "ssh"
        elif normalized_transport == "pysnmp":
            normalized_transport = "snmp"
        elif normalized_transport == "httpx":
            normalized_transport = "http"

        profile_transports = {t.lower() for t in profile.transport_types}
        if (
            normalized_transport not in profile_transports
            and effective_transport.lower() not in profile_transports
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Credential profile does not support target transport '{effective_transport}'.",
            )

        changes["credential_profile_id"] = str(profile.id)
        changes["credential_reference"] = profile.provider_reference or str(profile.id)

    try:
        updated_record = target_repo.update(
            tenant_id=tenant_id,
            target_id=target_id,
            **changes,
        )
        db_session.commit()
    except DiscoveryResourceNotFoundError as exc:
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DiscoveryPersistenceError as exc:
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _target_response(updated_record)



@router.get(
    "/credential-profiles",
    response_model=list[CredentialProfileResponse],
    summary="List credential profiles",
)
def list_credential_profiles(
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:target:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> list[CredentialProfileResponse]:
    return [
        _credential_profile_response(record)
        for record in CredentialProfileRepository(db_session).list(tenant_id=tenant_id)
    ]

@router.post(
    "/credential-profiles",
    response_model=CredentialProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a credential profile",
)
def create_credential_profile(
    payload: CredentialProfileRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:target:write"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> CredentialProfileResponse:
    record = CredentialProfileRepository(db_session).create(
        tenant_id=tenant_id,
        name=payload.name,
        provider_reference=payload.provider_reference,
        transport_types=payload.transport_types,
        description=payload.description,
    )
    db_session.commit()
    return _credential_profile_response(record)


@router.post(
    "/jobs",
    response_model=DiscoveryJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a discovery job",
)
def create_job(
    payload: DiscoveryJobRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[User, Depends(require_permission("discovery:job:submit"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    _: Annotated[object, Depends(get_application_container)],
) -> DiscoveryJobResponse:
    target = DiscoveryTargetRepository(db_session).get(
        tenant_id=tenant_id, target_id=payload.target_id
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Discovery target was not found.")
    if not target.enabled:
        raise HTTPException(status_code=409, detail="Discovery target is disabled.")

    run = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_identifier=target.identifier,
        target_address=target.address,
        status="started",
        metadata_json={"job_request": payload.metadata},
    )
    db_session.add(run)
    db_session.flush()
    try:
        job = DiscoveryJobRepository(db_session).create(
            tenant_id=tenant_id,
            target_id=target.id,
            run_id=run.id,
            requested_capabilities=payload.requested_capabilities,
            timeout_seconds=payload.timeout_seconds,
            correlation_id=payload.correlation_id,
            created_by=user.id,
        )
        db_session.commit()
    except DiscoveryPersistenceError as exc:
        db_session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return _job_response(job)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=DiscoveryJobResponse,
    summary="Request cooperative cancellation of a discovery job",
)
def cancel_job(
    job_id: UUID,
    payload: DiscoveryJobCancellationRequest,
    request: Request,
    response: Response,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[User, Depends(require_permission("discovery:job:cancel"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> DiscoveryJobResponse:
    jobs = DiscoveryJobRepository(db_session)
    try:
        job, changed = jobs.request_cancellation(
            tenant_id=tenant_id,
            job_id=job_id,
            requested_by=user.id,
            reason=payload.reason,
        )
        db_session.commit()
    except DiscoveryCancellationConflictError as exc:
        db_session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DiscoveryPersistenceError as exc:
        db_session.rollback()
        raise HTTPException(
            status_code=404, detail="Discovery job was not found."
        ) from exc

    audit_service.record_api_activity(
        event_type="discovery.job_cancel_requested",
        actor_id=user.id,
        tenant_id=tenant_id,
        resource_type="discovery_job",
        resource_id=str(job.id),
        outcome="cancelled" if job.state == "cancelled" else "requested",
        request_id=request.headers.get("X-Request-ID"),
        metadata={
            "reason": payload.reason,
            "changed": changed,
            "requested_at": (
                job.cancellation_requested_at.isoformat()
                if job.cancellation_requested_at is not None
                else None
            ),
        },
    )
    if job.state == DiscoveryJobStatus.RUNNING.value:
        response.status_code = status.HTTP_202_ACCEPTED
    return _job_response(job)


@router.post(
    "/jobs/{job_id}/cancel/force",
    response_model=DiscoveryJobResponse,
    summary="Resolve stale discovery job cancellation",
)
def resolve_job_cancellation(
    job_id: UUID,
    request: Request,
    response: Response,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[User, Depends(require_permission("discovery:job:cancel:force"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> DiscoveryJobResponse:
    jobs = DiscoveryJobRepository(db_session)
    try:
        job = jobs.resolve_stale_cancellation(
            tenant_id=tenant_id,
            job_id=job_id,
        )
        db_session.commit()
    except DiscoveryCancellationConflictError as exc:
        db_session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DiscoveryPersistenceError as exc:
        db_session.rollback()
        raise HTTPException(
            status_code=404, detail="Discovery job was not found."
        ) from exc

    audit_service.record_api_activity(
        event_type="discovery.job_cancellation_resolved",
        actor_id=user.id,
        tenant_id=tenant_id,
        resource_type="discovery_job",
        resource_id=str(job.id),
        outcome="cancelled",
        request_id=request.headers.get("X-Request-ID"),
        metadata={
            "resolved_at": (
                job.completed_at.isoformat()
                if job.completed_at is not None
                else None
            ),
            "reason": job.cancellation_reason,
        },
    )
    return _job_response(job)


@router.get(
    "/jobs",
    response_model=DiscoveryJobListResponse,
    summary="List discovery jobs",
)
def list_jobs(
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:job:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    q: str | None = Query(default=None, description="Free-text search across job/run/target fields"),
    status: str | None = Query(default=None, description="Filter by job status"),
    target_id: UUID | None = Query(default=None, description="Filter by target UUID"),
    date_from: datetime | None = Query(default=None, description="Filter jobs requested on or after timestamp"),
    date_to: datetime | None = Query(default=None, description="Filter jobs requested on or before timestamp"),
    sort: str | None = Query(default=None, description="Sort field (e.g. requested_at, started_at, completed_at, duration, target, status)"),
    order: str | None = Query(default=None, description="Sort order: asc or desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> DiscoveryJobListResponse:
    try:
        records, total = DiscoveryJobRepository(db_session).list_page(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            q=q,
            status=status,
            target_id=target_id,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
            order=order,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            if hasattr(status, "HTTP_422_UNPROCESSABLE_ENTITY")
            else 422,
            detail=str(exc),
        ) from exc

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return DiscoveryJobListResponse(
        items=[_job_response(record) for record in records],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page * page_size < total,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=DiscoveryJobResponse,
    summary="Get discovery job status",
)
def get_job(
    job_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:job:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> DiscoveryJobResponse:
    job = DiscoveryJobRepository(db_session).get(tenant_id=tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Discovery job was not found.")
    return _job_response(job)


@router.get(
    "/jobs/{job_id}/evidence",
    response_model=list[DiscoveryEvidenceResponse],
    summary="List evidence for a discovery job",
)
def get_job_evidence(
    job_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:evidence:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> list[DiscoveryEvidenceResponse]:
    jobs = DiscoveryJobRepository(db_session)
    if jobs.get(tenant_id=tenant_id, job_id=job_id) is None:
        raise HTTPException(status_code=404, detail="Discovery job was not found.")
    return [
        _evidence_response(record)
        for record in DiscoveryEvidenceRepository(db_session).list_for_job(
            tenant_id=tenant_id, job_id=job_id
        )
    ]


@router.get(
    "/jobs/{job_id}/devices",
    response_model=list[DiscoveryDeviceResultResponse],
    summary="List per-device discovery results",
)
def get_job_devices(
    job_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:job:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> list[DiscoveryDeviceResultResponse]:
    job = DiscoveryJobRepository(db_session).get(tenant_id=tenant_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Discovery job was not found.")
    records = db_session.scalars(
        select(DiscoveryDeviceResultRecord).where(
            DiscoveryDeviceResultRecord.tenant_id == tenant_id,
            DiscoveryDeviceResultRecord.discovery_job_id == job_id,
        )
    ).all()
    snapshot_models = db_session.execute(
        select(SnapshotDeviceRecord.management_ip, SnapshotDeviceRecord.model)
        .join(SnapshotRecord)
        .where(
            SnapshotRecord.discovery_run_id == job.run_id,
            SnapshotRecord.source == "live",
        )
    ).all()
    models_by_management_ip = {
        management_ip: model
        for management_ip, model in snapshot_models
        if management_ip is not None
    }
    return [
        DiscoveryDeviceResultResponse.model_validate(
            {
                "result_id": record.id,
                "address": record.address,
                "hostname": record.hostname,
                "vendor": record.vendor,
                "model": models_by_management_ip.get(record.address),
                "platform": record.platform,
                "state": record.state,
                "selected_transport": record.selected_transport,
                "failure_code": record.failure_code,
                "failure_message": record.failure_message,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "correlation_id": record.correlation_id,
            }
        )
        for record in records
    ]


@router.get(
    "/devices/{result_id}/attempts",
    response_model=list[DiscoveryTransportAttemptResponse],
    summary="List transport attempts for a discovered device",
)
def get_device_attempts(
    result_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:job:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> list[DiscoveryTransportAttemptResponse]:
    records = db_session.scalars(
        select(DiscoveryTransportAttemptRecord).where(
            DiscoveryTransportAttemptRecord.device_result_id == result_id,
            DiscoveryTransportAttemptRecord.tenant_id == tenant_id,
        )
    ).all()
    return [
        DiscoveryTransportAttemptResponse.model_validate(
            {
                "attempt_id": record.id,
                "transport": record.transport,
                "attempt_order": record.attempt_order,
                "result": record.result,
                "failure_code": record.failure_code,
                "duration_ms": record.duration_ms,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
                "correlation_id": record.correlation_id,
            }
        )
        for record in records
    ]


async def _execute_job(
    tenant_id: str,
    job_id: UUID,
    collector_registry: CollectorRegistry,
    parser_pipeline: ParserPipeline,
    normalization_engine: NormalizationEngine,
    execution_owner: UUID,
    lease_seconds: float,
    already_claimed: bool = False,
    lease_lost: Callable[[], bool] | None = None,
) -> None:
    db_session = SessionLocal()
    try:
        job = DiscoveryJobRepository(db_session).get(tenant_id=tenant_id, job_id=job_id)
        if job is None or job.state == DiscoveryJobStatus.CANCELLED.value:
            return
        target = DiscoveryTargetRepository(db_session).get(
            tenant_id=tenant_id, target_id=job.target_id
        )
        if target is not None and target.scope_type in {"ip_range", "cidr_network"}:
            try:
                if not already_claimed:
                    DiscoveryJobRepository(db_session).claim(
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
                jobs = DiscoveryJobRepository(db_session)
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
                jobs = DiscoveryJobRepository(db_session)
                if not jobs.cancellation_requested(tenant_id=tenant_id, job_id=job_id):
                    raise
                jobs.finalise_cancellation(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    expected_execution_owner=execution_owner,
                )
                db_session.commit()
        else:
            service = DiscoveryExecutionService(
                db_session,
                collector_registry,
                parser_pipeline=parser_pipeline,
                normalization_engine=normalization_engine,
            )
            await service.execute(
                tenant_id=tenant_id,
                job_id=job_id,
                execution_owner=execution_owner,
                lease_seconds=lease_seconds,
                already_claimed=already_claimed,
                lease_lost=lease_lost,
            )
    finally:
        db_session.close()


def _validate_tenant(payload_tenant: str, header_tenant: str) -> None:
    if payload_tenant != header_tenant:
        raise HTTPException(status_code=403, detail="Tenant scope mismatch.")


def _target_response(record: DiscoveryTargetRecord) -> DiscoveryTargetResponse:
    return DiscoveryTargetResponse.model_validate(
        {
            "target_id": record.id,
            "tenant_id": record.tenant_id,
            "identifier": record.identifier,
            "address": record.address,
            "scope_type": record.scope_type,
            "scope_end": record.scope_end,
            "scope_cidr": record.scope_cidr,
            "hostname": record.hostname,
            "vendor": record.vendor,
            "platform_hint": record.platform_hint,
            "preferred_transport": record.preferred_transport,
            "allowed_fallback_transports": record.allowed_fallback_transports,
            "credential_references": list(record.credential_references),
            "credential_profile_id": record.credential_profile_id,
            "enabled": record.enabled,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _job_response(record: DiscoveryJobRecord) -> DiscoveryJobResponse:
    target_identifier = None
    target_address = None
    if getattr(record, "target", None) is not None:
        target_identifier = record.target.identifier
        target_address = record.target.address

    return DiscoveryJobResponse.model_validate(
        {
            "job_id": record.id,
            "tenant_id": record.tenant_id,
            "target_id": record.target_id,
            "target_identifier": target_identifier,
            "target_address": target_address,
            "discovery_run_id": record.run_id,
            "status": record.state,
            "selected_transport": record.selected_transport,
            "selected_platform": record.selected_platform,
            "attempts": record.attempts,
            "error_code": record.failure_code,
            "error_message": record.failure_message,
            "created_at": record.requested_at,
            "queued_at": record.requested_at,
            "started_at": record.started_at,
            "finished_at": record.completed_at,
            "timeout_seconds": record.timeout_seconds,
            "correlation_id": record.correlation_id,
            "cancellation_requested_at": record.cancellation_requested_at,
            "cancellation_requested_by": record.cancellation_requested_by,
            "cancellation_reason": record.cancellation_reason,
            "execution_owner": record.execution_owner,
            "lease_expires_at": record.lease_expires_at,
            "last_heartbeat_at": record.last_heartbeat_at,
            "has_active_lease": bool(
                record.execution_owner is not None
                and record.lease_expires_at is not None
                and (
                    record.lease_expires_at.replace(tzinfo=UTC)
                    if record.lease_expires_at.tzinfo is None
                    else record.lease_expires_at
                )
                > datetime.now(UTC)
            ),
        }
    )


def _credential_profile_response(
    record: object,
) -> CredentialProfileResponse:
    return CredentialProfileResponse.model_validate(
        {
            "profile_id": record.id,
            "tenant_id": record.tenant_id,
            "name": record.name,
            "description": record.description,
            "transport_types": list(record.transport_types),
            "provider_reference": record.provider_reference,
            "enabled": record.enabled,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )


def _evidence_response(record: DiscoveryEvidenceRecord) -> DiscoveryEvidenceResponse:
    return DiscoveryEvidenceResponse.model_validate(
        {
            "evidence_id": record.id,
            "tenant_id": record.tenant_id,
            "target_id": record.target_id,
            "discovery_job_id": record.job_id,
            "discovery_run_id": record.run_id,
            "collector_name": record.collector,
            "platform": "unknown",
            "transport": "unknown",
            "evidence_type": record.evidence_type,
            "command_or_probe": record.command_or_probe,
            "payload": record.payload,
            "captured_at": record.observed_at,
            "sequence": record.sequence,
            "parser_version": record.parser_version,
            "normalization_version": record.normalization_version,
            "content_hash": record.payload_hash,
        }
    )


@router.get("", summary="Discovery operations", response_model=dict[str, str])
def discovery_root() -> dict[str, str]:
    return {"status": "available"}
