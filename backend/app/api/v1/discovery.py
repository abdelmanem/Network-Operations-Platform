"""M31.4 discovery API boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_application_container, get_db_session
from backend.app.auth.api.dependencies import require_permission
from backend.app.auth.domain.models import User
from backend.app.collectors.registry import CollectorRegistry
from backend.app.database.session import SessionLocal
from backend.app.discovery.execution import DiscoveryExecutionService
from backend.app.persistence.discovery_repositories import (
    DiscoveryEvidenceRepository,
    DiscoveryJobRepository,
    DiscoveryPersistenceError,
    DiscoveryTargetRepository,
)
from backend.app.persistence.models import (
    DiscoveryEvidenceRecord,
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)
from backend.app.schemas.discovery import (
    DiscoveryEvidenceResponse,
    DiscoveryJobRequest,
    DiscoveryJobResponse,
    DiscoveryTargetRequest,
    DiscoveryTargetResponse,
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


@router.post(
    "/jobs",
    response_model=DiscoveryJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a discovery job",
)
def create_job(
    payload: DiscoveryJobRequest,
    background_tasks: BackgroundTasks,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:job:submit"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    container: Annotated[object, Depends(get_application_container)],
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
        )
        db_session.commit()
    except DiscoveryPersistenceError as exc:
        db_session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_container = cast("ApplicationContainer", container)
    background_tasks.add_task(
        _execute_job,
        tenant_id,
        job.id,
        runtime_container.discovery_collector_registry,
    )
    return _job_response(job)


@router.get(
    "/jobs",
    response_model=list[DiscoveryJobResponse],
    summary="List discovery jobs",
)
def list_jobs(
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("discovery:job:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> list[DiscoveryJobResponse]:
    return [
        _job_response(record)
        for record in DiscoveryJobRepository(db_session).list(tenant_id=tenant_id)
    ]


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


async def _execute_job(
    tenant_id: str,
    job_id: UUID,
    collector_registry: CollectorRegistry,
) -> None:
    db_session = SessionLocal()
    try:
        service = DiscoveryExecutionService(db_session, collector_registry)
        await service.execute(tenant_id=tenant_id, job_id=job_id)
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
    return DiscoveryJobResponse.model_validate(
        {
            "job_id": record.id,
            "tenant_id": record.tenant_id,
            "target_id": record.target_id,
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
