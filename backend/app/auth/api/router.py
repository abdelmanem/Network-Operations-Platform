from __future__ import annotations

from typing import Annotated

from backend.app.auth.api.dependencies import get_auth_service, get_current_user
from backend.app.auth.api.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.app.auth.application.services import AuthenticationService
from backend.app.auth.domain.models import User
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: RegisterRequest,
    auth_service: Annotated[AuthenticationService, Depends(get_auth_service)],
) -> UserResponse:
    try:
        user = auth_service.register_user(
            username=payload.username,
            email=str(payload.email),
            password=payload.password,
            roles=payload.roles,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return UserResponse(
        username=user.username,
        email=user.email,
        roles=[role.name for role in user.roles],
        permissions=list({p.name for r in user.roles for p in r.permissions}),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    auth_service: Annotated[AuthenticationService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        token_pair = auth_service.authenticate_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
    )


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(
        username=user.username,
        email=user.email,
        roles=[role.name for role in user.roles],
        permissions=list({p.name for r in user.roles for p in r.permissions}),
    )
