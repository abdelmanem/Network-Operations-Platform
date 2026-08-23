"""Credential profile API for secret-safe network discovery."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session, get_secret_provider
from backend.app.auth.api.dependencies import require_permission
from backend.app.auth.domain.models import User
from backend.app.persistence.discovery_repositories import CredentialProfileRepository
from backend.app.persistence.models import CredentialProfileRecord
from backend.app.schemas.discovery import (
    CredentialProfileRequest,
    CredentialProfileResponse,
    CredentialProfileTestRequest,
    CredentialProfileTestResponse,
    CredentialProfileUpdateRequest,
)
from backend.app.transports.credentials import SecretProvider
from backend.app.transports.secret_errors import SecretProviderError

router: APIRouter = APIRouter(prefix="/credentials", tags=["credentials"])


@router.get(
    "/profiles",
    response_model=list[CredentialProfileResponse],
    summary="List credential profiles",
)
def list_profiles(
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("credential:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> list[CredentialProfileResponse]:
    return [
        _profile_response(record)
        for record in CredentialProfileRepository(db_session).list(tenant_id=tenant_id)
    ]


@router.post(
    "/profiles",
    response_model=CredentialProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a credential profile",
)
def create_profile(
    payload: CredentialProfileRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("credential:write"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> CredentialProfileResponse:
    record = CredentialProfileRepository(db_session).create(
        tenant_id=tenant_id,
        name=payload.name,
        provider_reference=payload.provider_reference,
        transport_types=payload.transport_types,
        description=payload.description,
        vendor=payload.vendor,
        platform=payload.platform,
        credential_type=payload.credential_type,
        username=payload.username,
    )
    db_session.commit()
    return _profile_response(record)


@router.get(
    "/profiles/{profile_id}",
    response_model=CredentialProfileResponse,
    summary="Get a credential profile",
)
def get_profile(
    profile_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("credential:read"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> CredentialProfileResponse:
    record = CredentialProfileRepository(db_session).get(
        tenant_id=tenant_id,
        profile_id=profile_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Credential profile was not found.")
    return _profile_response(record)


@router.patch(
    "/profiles/{profile_id}",
    response_model=CredentialProfileResponse,
    summary="Update a credential profile",
)
def update_profile(
    profile_id: UUID,
    payload: CredentialProfileUpdateRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("credential:write"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> CredentialProfileResponse:
    record = CredentialProfileRepository(db_session).update(
        tenant_id=tenant_id,
        profile_id=profile_id,
        name=payload.name,
        description=payload.description,
        vendor=payload.vendor,
        platform=payload.platform,
        credential_type=payload.credential_type,
        username=payload.username,
        transport_types=payload.transport_types,
        enabled=payload.enabled,
    )
    db_session.commit()
    return _profile_response(record)


@router.delete(
    "/profiles/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a credential profile",
)
def delete_profile(
    profile_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("credential:write"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
) -> None:
    deleted = CredentialProfileRepository(db_session).delete(
        tenant_id=tenant_id,
        profile_id=profile_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential profile was not found.")
    db_session.commit()


@router.post(
    "/profiles/{profile_id}/test",
    response_model=CredentialProfileTestResponse,
    summary="Test a credential profile against a target transport",
)
def test_profile(
    profile_id: UUID,
    payload: CredentialProfileTestRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permission("credential:write"))],
    tenant_id: Annotated[str, Header(alias="X-Tenant-ID")],
    secret_provider: Annotated[SecretProvider, Depends(get_secret_provider)],
) -> CredentialProfileTestResponse:
    record = CredentialProfileRepository(db_session).get(
        tenant_id=tenant_id,
        profile_id=profile_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Credential profile was not found.")

    compatibility = _validate_profile_for_transport(record, payload.transport)
    if compatibility[0] != "success":
        return CredentialProfileTestResponse(
            status=compatibility[0],
            transport=payload.transport,
            target=payload.target,
            credential_type=record.credential_type,
            message=compatibility[1],
            provider_reference=record.provider_reference,
        )

    try:
        secret_provider.resolve_secret(record.provider_reference)
    except SecretProviderError as exc:
        return CredentialProfileTestResponse(
            status=exc.code,
            transport=payload.transport,
            target=payload.target,
            credential_type=record.credential_type,
            message=exc.message,
            provider_reference=record.provider_reference,
        )

    return CredentialProfileTestResponse(
        status="success",
        transport=payload.transport,
        target=payload.target,
        credential_type=record.credential_type,
        message="Credential profile resolved successfully for the selected transport.",
        provider_reference=record.provider_reference,
    )


def _validate_profile_for_transport(
    record: CredentialProfileRecord,
    transport: str,
) -> tuple[str, str]:
    valid_transport_to_types = {
        "ssh": {"ssh_password", "ssh_key"},
        "snmp": {"snmp_v2c", "snmp_v3"},
        "telnet": {"telnet_password"},
        "http": {"http_basic", "http_token"},
        "https": {"http_basic", "http_token"},
        "icmp": {"icmp"},
    }
    expected = valid_transport_to_types.get(transport)
    if expected is None:
        return "unsupported_transport", "The requested transport is not supported by the credential execution boundary."
    credential_type = record.credential_type or ""
    if credential_type not in expected:
        return "invalid_credential_profile", (
            f"Credential type '{credential_type or 'unknown'}' is not compatible with transport '{transport}'."
        )
    if transport not in (record.transport_types or []):
        return "invalid_credential_profile", (
            f"Credential profile does not allow transport '{transport}'."
        )
    return "success", "Credential profile is compatible with the requested transport."


def _profile_response(record: CredentialProfileRecord) -> CredentialProfileResponse:
    return CredentialProfileResponse.model_validate(
        {
            "profile_id": record.id,
            "tenant_id": record.tenant_id,
            "name": record.name,
            "description": record.description,
            "vendor": record.vendor,
            "platform": record.platform,
            "credential_type": record.credential_type,
            "username": record.username,
            "transport_types": list(record.transport_types),
            "provider_reference": record.provider_reference,
            "secret_status": record.secret_status,
            "enabled": record.enabled,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
    )
