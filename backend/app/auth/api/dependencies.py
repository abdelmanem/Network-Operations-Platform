from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Annotated

from backend.app.auth.application.services import (
    AuthenticationService,
    AuthorizationService,
    PasswordHashingService,
    TokenService,
)
from backend.app.auth.domain.models import User
from backend.app.auth.infrastructure.repositories import (
    SQLAlchemyAuditEventRepository,
    SQLAlchemyPermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyUserRepository,
)
from backend.app.config.settings import get_settings
from backend.app.database.session import SessionLocal
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

bearer_scheme = HTTPBearer(auto_error=False)


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_auth_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> AuthenticationService:
    user_repo = SQLAlchemyUserRepository(db)
    role_repo = SQLAlchemyRoleRepository(db)
    permission_repo = SQLAlchemyPermissionRepository(db)
    audit_repo = SQLAlchemyAuditEventRepository(db)
    settings = get_settings()
    return AuthenticationService(
        user_repository=user_repo,
        role_repository=role_repo,
        permission_repository=permission_repo,
        audit_repository=audit_repo,
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key=settings.auth_secret_key),
        access_token_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_token_ttl_seconds=settings.refresh_token_ttl_seconds,
    )


def get_authorization_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> AuthorizationService:
    user_repo = SQLAlchemyUserRepository(db)
    role_repo = SQLAlchemyRoleRepository(db)
    return AuthorizationService(user_repository=user_repo, role_repository=role_repo)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    auth_service: Annotated[AuthenticationService, Depends(get_auth_service)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )
    user = auth_service.get_current_user(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user


def require_permission(permission_name: str) -> Callable[..., User]:
    def dependency(
        user: Annotated[User, Depends(get_current_user)],
        authz: Annotated[AuthorizationService, Depends(get_authorization_service)],
    ) -> User:
        if not authz.authorize(user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )
        return user

    return dependency
