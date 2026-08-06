from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from uuid import UUID

from backend.app.auth.domain.models import Role, TokenPair, User
from backend.app.auth.infrastructure.repositories import (
    AuditEventRepository,
    PermissionRepository,
    RoleRepository,
    UserRepository,
)


class PasswordHashingService:
    """Hash and verify passwords using PBKDF2-HMAC-SHA256."""

    def __init__(self, iterations: int = 200_000) -> None:
        self.iterations = iterations

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            self.iterations,
        )
        return json.dumps(
            {
                "alg": "pbkdf2_sha256",
                "iterations": self.iterations,
                "salt": salt.hex(),
                "hash": derived.hex(),
            }
        )

    def verify_password(self, password: str, password_hash: str) -> bool:
        payload = json.loads(password_hash)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(payload["salt"]),
            payload["iterations"],
        )
        return hmac.compare_digest(derived.hex(), payload["hash"])


class TokenService:
    """Encode and decode signed JWT-like tokens."""

    def __init__(self, secret_key: str | None = None) -> None:
        self.secret_key = secret_key or "development-secret"

    def _sign(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        signature = hashlib.sha256(body + self.secret_key.encode("utf-8")).hexdigest()
        return f"{body.decode('utf-8')}.{signature}"

    def _verify(self, token: str) -> dict[str, Any]:
        body, signature = token.rsplit(".", 1)
        expected = hashlib.sha256(
            body.encode("utf-8") + self.secret_key.encode("utf-8")
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid token signature")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("Invalid token payload")
        return payload

    def encode(self, claims: dict[str, Any], *, expires_in_seconds: int) -> str:
        now = int(time.time())
        payload = dict(claims)
        payload["iat"] = now
        payload["exp"] = now + expires_in_seconds
        return self._sign(payload)

    def decode(self, token: str) -> dict[str, Any]:
        payload = self._verify(token)
        if int(payload["exp"]) <= int(time.time()):
            raise ValueError("Token expired")
        return payload


class AuthenticationService:
    """Authenticate users and issue tokens."""

    def __init__(
        self,
        *,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        permission_repository: PermissionRepository,
        audit_repository: AuditEventRepository,
        password_service: PasswordHashingService,
        token_service: TokenService,
        access_token_ttl_seconds: int = 900,
        refresh_token_ttl_seconds: int = 2_592_000,
    ) -> None:
        self.user_repository = user_repository
        self.role_repository = role_repository
        self.permission_repository = permission_repository
        self.audit_repository = audit_repository
        self.password_service = password_service
        self.token_service = token_service
        self.access_token_ttl_seconds = access_token_ttl_seconds
        self.refresh_token_ttl_seconds = refresh_token_ttl_seconds

    def register_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> User:
        existing = self.user_repository.get_by_username(username)
        if existing is not None:
            raise ValueError("User already exists")

        resolved_roles: list[Role] = []
        if roles:
            for role_name in roles:
                role = self.role_repository.get_by_name(role_name)
                if role is None:
                    raise ValueError(f"Role not found: {role_name}")
                resolved_roles.append(role)

        user = self.user_repository.create(
            username=username,
            email=email,
            password_hash=self.password_service.hash_password(password),
            roles=resolved_roles,
        )
        self.audit_repository.create(
            event_type="user_registered",
            subject_id=user.id,
            metadata={"username": username},
        )
        return user

    def authenticate_user(self, username: str, password: str) -> TokenPair:
        user = self.user_repository.get_by_username(username)
        if user is None or not self.password_service.verify_password(
            password, user.password_hash
        ):
            raise ValueError("Invalid credentials")
        if not user.is_active:
            raise ValueError("User is inactive")

        access_token = self.token_service.encode(
            {
                "sub": str(user.id),
                "type": "access",
                "username": user.username,
            },
            expires_in_seconds=self.access_token_ttl_seconds,
        )
        refresh_token = self.token_service.encode(
            {
                "sub": str(user.id),
                "type": "refresh",
                "username": user.username,
            },
            expires_in_seconds=self.refresh_token_ttl_seconds,
        )
        self.audit_repository.create(
            event_type="login",
            subject_id=user.id,
            metadata={"username": user.username},
        )
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    def refresh_access_token(self, refresh_token: str) -> TokenPair:
        claims = self.token_service.decode(refresh_token)
        if claims.get("type") != "refresh":
            raise ValueError("Invalid token type")
        user_id = UUID(str(claims["sub"]))
        user = self.user_repository.get(user_id)
        if user is None or not user.is_active:
            raise ValueError("Invalid refresh token")
        access_token = self.token_service.encode(
            {"sub": str(user.id), "type": "access", "username": user.username},
            expires_in_seconds=900,
        )
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    def get_current_user(self, token: str) -> User | None:
        try:
            claims = self.token_service.decode(token)
        except ValueError:
            return None
        if claims.get("type") != "access":
            return None
        user_id = UUID(str(claims["sub"]))
        return self.user_repository.get(user_id)


class AuthorizationService:
    """Check whether a user has access to a given permission."""

    def __init__(
        self,
        *,
        user_repository: UserRepository,
        role_repository: RoleRepository,
    ) -> None:
        self.user_repository = user_repository
        self.role_repository = role_repository

    def authorize(self, user: User, permission_name: str) -> bool:
        return any(
            permission.name == permission_name
            for role in user.roles
            for permission in role.permissions
        )
