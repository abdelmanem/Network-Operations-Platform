from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_application_container, get_db_session
from backend.app.api.v1.exceptions import NetBoxIntegrationError
from backend.app.audit.api.router import get_audit_service
from backend.app.audit.application.services import AuditService
from backend.app.auth.api.dependencies import get_current_user, require_permission
from backend.app.auth.domain.models import User
from backend.app.integrations.netbox.exceptions import (
    NetBoxResponseError,
    NetBoxTransportError,
    NetBoxValidationError,
    NetBoxVersionMismatchError,
)
from backend.app.persistence.repositories import SnapshotRepository
from backend.app.schemas.integrations import (
    InventoryCounts,
    NetBoxIntegrationStatusResponse,
    NetBoxSyncResponse,
    NetBoxTestConnectionResponse,
)

logger = logging.getLogger("backend.app.api.integrations")
router = APIRouter(prefix="/integrations/netbox", tags=["integrations"])


def _handle_netbox_error(exc: Exception) -> None:
    """Helper to catch and translate NetBox client errors to API exceptions."""
    logger.exception("NetBox integration error occurred")
    if isinstance(exc, NetBoxResponseError):
        if exc.status_code in (401, 403):
            raise NetBoxIntegrationError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="NETBOX_AUTHENTICATION_FAILED",
                message=(
                    "NetBox Authentication Failed: The NetBox server is reachable, "
                    "but authentication failed."
                ),
            )
        raise NetBoxIntegrationError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="NETBOX_UNREACHABLE",
            message=f"NetBox response error: {exc.detail}",
        )
    elif isinstance(exc, NetBoxTransportError):
        err_msg = str(exc)
        if any(term in err_msg.lower() for term in ("cert", "ssl", "verify")):
            raise NetBoxIntegrationError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="NETBOX_TLS_VALIDATION_FAILED",
                message=(
                    "NetBox Connection Failed: The NetBox server certificate "
                    "could not be validated."
                ),
            )
        raise NetBoxIntegrationError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="NETBOX_UNREACHABLE",
            message="NetBox Unreachable: The NetBox API could not be reached.",
        )
    elif isinstance(exc, NetBoxVersionMismatchError):
        raise NetBoxIntegrationError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="NETBOX_VERSION_MISMATCH",
            message=f"Unsupported NetBox Version: {exc}",
        )
    elif isinstance(exc, NetBoxValidationError):
        raise NetBoxIntegrationError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="NETBOX_VERSION_MISMATCH",
            message=f"NetBox Validation Failed: {exc}",
        )
    else:
        raise NetBoxIntegrationError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="NETBOX_SYNC_FAILED",
            message=f"NetBox error: {exc}",
        )


async def run_netbox_sync_background(
    job_id: UUID,
    db_session: Session,
    container: Any,  # noqa: ANN401 - container is intentionally dynamic
    actor_id: UUID,
    audit_service: AuditService,
    tenant_id: str = "default",
) -> None:
    """FastAPI background task to execute NetBox inventory synchronization."""
    repo = SnapshotRepository(db_session)
    job = repo.get_sync_job(job_id)
    if job is None:
        logger.error(f"Sync job {job_id} not found in database.")
        return

    # Update job state to 'running'
    job.status = "running"
    job.started_at = datetime.now(UTC)
    db_session.commit()

    try:
        # Access the workflow engine to get the inventory service
        inventory_service = container.engine.workflow.inventory_service
        snapshot = await inventory_service.synchronize(force_refresh=True)

        # Persist the snapshot in PostgreSQL database using repo.add_netbox_snapshot
        # Wrap in try/except to ensure atomicity: if add fails, rollback all pending changes
        try:
            repo.add_netbox_snapshot(snapshot, tenant_id=tenant_id)
            db_session.commit()  # Commit snapshot atomically
        except Exception as snapshot_exc:
            logger.exception("Failed to persist NetBox snapshot")
            db_session.rollback()  # Roll back pending snapshot records
            raise snapshot_exc  # Re-raise to outer except handler

        # Update sync job state to 'succeeded' in a separate transaction
        job.status = "succeeded"
        job.finished_at = datetime.now(UTC)
        db_session.commit()

        # Log audit record
        audit_service.record_api_activity(
            event_type="netbox.inventory_sync",
            actor_id=actor_id,
            resource_type="netbox_sync",
            resource_id=str(job_id),
            outcome="success",
            metadata={
                "job_id": str(job_id),
                "device_count": len(snapshot.devices),
            },
        )
    except Exception as exc:
        logger.exception("NetBox sync background task failed")
        # At this point, if snapshot add failed, it was already rolled back.
        # Now update job status to failed in a clean transaction.
        try:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
            job.error_message = str(exc)
            db_session.commit()
        except Exception as job_update_exc:  # pragma: no cover - defensive
            logger.exception("Failed to update sync job to failed state")
            db_session.rollback()

        # Log audit record
        audit_service.record_api_activity(
            event_type="netbox.inventory_sync",
            actor_id=actor_id,
            resource_type="netbox_sync",
            resource_id=str(job_id),
            outcome="failed",
            metadata={
                "job_id": str(job_id),
                "error": str(exc),
            },
        )


@router.get("/status", response_model=NetBoxIntegrationStatusResponse)
def get_status(
    request: Request,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("inventory:read"))],
) -> NetBoxIntegrationStatusResponse:
    """Safe connection status and inventory count reporting."""
    container = get_application_container(request)
    settings = container.settings
    repo = SnapshotRepository(db_session)

    # Base configuration info (checking configured status)
    configured = bool(settings.netbox_base_url)

    # Get latest NetBox snapshot metadata and counts
    latest_snapshot = repo.get_latest("netbox")
    last_successful_sync = None
    counts = InventoryCounts(devices=0, interfaces=0, ip_addresses=0, vlans=0)

    if latest_snapshot is not None:
        last_successful_sync = latest_snapshot.captured_at
        payload = latest_snapshot.payload
        if isinstance(payload, dict):
            counts = InventoryCounts(
                devices=len(payload.get("devices", [])),
                interfaces=len(payload.get("interfaces", [])),
                ip_addresses=len(payload.get("ip_addresses", [])),
                vlans=len(payload.get("vlans", [])),
            )

    # Get latest NetBox sync job status
    latest_job = repo.get_latest_sync_job()
    current_sync_status = "idle"
    sync_started_at = None
    sync_completed_at = None
    sync_error = None

    if latest_job is not None:
        current_sync_status = latest_job.status
        sync_started_at = latest_job.started_at
        sync_completed_at = latest_job.finished_at
        sync_error = latest_job.error_message

    # Quick connectivity check is intentionally conservative. This endpoint reports
    # based on persisted snapshot evidence and settings rather than hard-failing when
    # the live service is unavailable.
    try:
        inventory_service = container.engine.workflow.inventory_service
        if inventory_service is None:
            logger.debug("NetBox status endpoint found no live inventory service.")
    except Exception as exc:
        logger.debug(
            "NetBox status endpoint could not inspect live runtime state: %s",
            exc,
        )

    # For status endpoint, we report connection based on latest snapshot or a quick
    # check. To keep this endpoint extremely fast, we fetch settings parameters and
    # connection details. If there is a latest snapshot, we can assume it was
    # previously verified. We can also quickly inspect settings:
    tls_verified = bool(settings.netbox_ca_cert)
    configured_token = bool(settings.netbox_token)

    return NetBoxIntegrationStatusResponse(
        configured=configured,
        connected=latest_snapshot is not None,
        tls_verified=tls_verified,
        authenticated=configured_token,
        version=settings.netbox_expected_version,
        hostname=(
            settings.netbox_base_url.split("//")[-1].split(":")[0]
            if configured
            else None
        ),
        last_successful_sync=last_successful_sync,
        current_sync_status=current_sync_status,
        sync_started_at=sync_started_at,
        sync_completed_at=sync_completed_at,
        sync_error=sync_error,
        inventory_counts=counts,
    )


@router.post("/test", response_model=NetBoxTestConnectionResponse)
async def test_connection(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    _: Annotated[User, Depends(require_permission("inventory:write"))],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
) -> NetBoxTestConnectionResponse:
    """Verify live NetBox health, expected version, authentication, and TLS."""
    container = get_application_container(request)
    inventory_service = container.engine.workflow.inventory_service

    try:
        health_resp = await inventory_service.netbox_service.health()
        version = health_resp.version or health_resp.api_version
        hostname = health_resp.hostname

        # Record successful audit log
        audit_service.record_api_activity(
            event_type="netbox.connection_test",
            actor_id=user.id,
            resource_type="netbox",
            resource_id="connection",
            outcome="success",
            metadata={"version": version, "hostname": hostname},
        )

        return NetBoxTestConnectionResponse(
            connected=True,
            tls_verified=bool(container.settings.netbox_ca_cert),
            authenticated=True,
            version=version,
            hostname=hostname,
            message="NetBox connection check successful.",
        )
    except Exception as exc:
        # Record failed audit log
        audit_service.record_api_activity(
            event_type="netbox.connection_test",
            actor_id=user.id,
            resource_type="netbox",
            resource_id="connection",
            outcome="failed",
            metadata={"error": str(exc)},
        )
        _handle_netbox_error(exc)
        raise  # pragma: no cover


@router.post(
    "/sync", status_code=status.HTTP_202_ACCEPTED, response_model=NetBoxSyncResponse
)
async def synchronize_inventory(
    request: Request,
    background_tasks: BackgroundTasks,
    db_session: Annotated[Session, Depends(get_db_session)],
    user: Annotated[User, Depends(get_current_user)],
    _: Annotated[User, Depends(require_permission("inventory:write"))],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    tenant_id: str = Header(default="default", alias="X-Tenant-ID"),
) -> NetBoxSyncResponse:
    """Submit a background job to synchronize NetBox expected state snapshot."""
    container = get_application_container(request)
    repo = SnapshotRepository(db_session)

    from backend.app.persistence.models import NetBoxSyncJobRecord
    from sqlalchemy import text
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.exc import OperationalError

    # Use database-level locking to prevent concurrent sync race condition.
    # For PostgreSQL: Use advisory locks (pg_advisory_lock)
    # For SQLite/testing: Use a simple status check
    
    NETBOX_SYNC_ADVISORY_LOCK_KEY = 42  # Arbitrary unique key for this lock
    use_advisory_lock = False
    
    # Try PostgreSQL advisory lock first (will fail gracefully on SQLite)
    try:
        db_session.execute(text(f"SELECT pg_advisory_lock({NETBOX_SYNC_ADVISORY_LOCK_KEY})"))
        use_advisory_lock = True
    except OperationalError:
        # SQLite doesn't support pg_advisory_lock, use simple status check instead
        use_advisory_lock = False
    
    try:
        # Check for active jobs (either under lock on PostgreSQL or directly on SQLite)
        active_job = (
            db_session.query(NetBoxSyncJobRecord)
            .filter(NetBoxSyncJobRecord.status.in_(["queued", "running"]))
            .first()
        )

        if active_job is not None:
            raise NetBoxIntegrationError(
                status_code=status.HTTP_409_CONFLICT,
                code="NETBOX_SYNC_ALREADY_RUNNING",
                message="Another NetBox synchronization is already in progress.",
            )

        # Create new sync job UUID and persist
        job_id = uuid4()
        repo.create_sync_job(job_id)
        db_session.commit()
    finally:
        # Release the advisory lock if we acquired it (PostgreSQL only)
        if use_advisory_lock:
            try:
                db_session.execute(
                    text(f"SELECT pg_advisory_unlock({NETBOX_SYNC_ADVISORY_LOCK_KEY})")
                )
            except OperationalError:
                pass  # Ignore if unlock fails (e.g., no lock was held)

    # Log submitted audit record
    audit_service.record_api_activity(
        event_type="netbox.inventory_sync",
        actor_id=user.id,
        resource_type="netbox_sync",
        resource_id=str(job_id),
        outcome="submitted",
        metadata={"job_id": str(job_id)},
    )

    # Dispatch to background task
    background_tasks.add_task(
        run_netbox_sync_background,
        job_id,
        db_session,
        container,
        user.id,
        audit_service,
        tenant_id,
    )

    return NetBoxSyncResponse(job_id=job_id, status="queued")
