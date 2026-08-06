from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from backend.app.auth.domain.models import AuditEvent, Permission, Role, User
from backend.app.auth.infrastructure.models import (
    AuthAuditEvent,
    AuthPermission,
    AuthRole,
    AuthUser,
)
from sqlalchemy.orm import Session


class UserRepository(ABC):
    @abstractmethod
    def get(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    def create(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        roles: list[Role] | None = None,
    ) -> User: ...


class RoleRepository(ABC):
    @abstractmethod
    def get_by_name(self, name: str) -> Role | None: ...

    @abstractmethod
    def create(self, *, name: str, description: str = "") -> Role: ...

    @abstractmethod
    def add_permission(self, role: Role, permission: Permission) -> None: ...


class PermissionRepository(ABC):
    @abstractmethod
    def create(self, *, name: str, description: str = "") -> Permission: ...


class AuditEventRepository(ABC):
    @abstractmethod
    def create(
        self,
        *,
        event_type: str,
        subject_id: UUID | None = None,
        actor_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent: ...

    @abstractmethod
    def list(self, *, limit: int = 50) -> list[AuditEvent]: ...


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: UUID) -> User | None:
        row = self.session.get(AuthUser, user_id)
        return self._to_domain(row) if row is not None else None

    def get_by_username(self, username: str) -> User | None:
        row = (
            self.session.query(AuthUser)
            .filter(AuthUser.username == username)
            .one_or_none()
        )
        return self._to_domain(row) if row is not None else None

    def create(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        roles: list[Role] | None = None,
    ) -> User:
        row = AuthUser(username=username, email=email, password_hash=password_hash)
        if roles:
            row.roles = [self._role_from_domain(role) for role in roles]
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        domain_user = self._to_domain(row)
        if domain_user is None:
            raise ValueError("User could not be created")
        return domain_user

    def _role_from_domain(self, role: Role) -> AuthRole:
        existing = (
            self.session.query(AuthRole)
            .filter(AuthRole.name == role.name)
            .one_or_none()
        )
        if existing is not None:
            return existing
        return AuthRole(name=role.name, description="")

    def _to_domain(self, row: AuthUser | None) -> User | None:
        if row is None:
            return None
        return User(
            id=row.id,
            username=row.username,
            email=row.email,
            password_hash=row.password_hash,
            is_active=row.is_active,
            roles=tuple(self._roles_to_domain(row.roles)),
        )

    def _roles_to_domain(self, rows: list[AuthRole] | None) -> list[Role]:
        if not rows:
            return []
        return [
            Role(
                id=row.id,
                name=row.name,
                description=row.description,
                permissions=tuple(
                    Permission(id=p.id, name=p.name, description=p.description)
                    for p in row.permissions
                ),
            )
            for row in rows
        ]


class SQLAlchemyRoleRepository(RoleRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_name(self, name: str) -> Role | None:
        row = self.session.query(AuthRole).filter(AuthRole.name == name).one_or_none()
        return self._to_domain(row) if row is not None else None

    def create(self, *, name: str, description: str = "") -> Role:
        row = AuthRole(name=name, description=description)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        domain_role = self._to_domain(row)
        if domain_role is None:
            raise ValueError("Role could not be created")
        return domain_role

    def add_permission(self, role: Role, permission: Permission) -> None:
        role_row = (
            self.session.query(AuthRole)
            .filter(AuthRole.name == role.name)
            .one_or_none()
        )
        permission_row = (
            self.session.query(AuthPermission)
            .filter(AuthPermission.name == permission.name)
            .one_or_none()
        )
        if role_row is None:
            raise ValueError("Role not found")
        if permission_row is None:
            raise ValueError("Permission not found")
        if permission_row not in role_row.permissions:
            role_row.permissions.append(permission_row)
        self.session.commit()

    def _to_domain(self, row: AuthRole | None) -> Role | None:
        if row is None:
            return None
        return Role(
            id=row.id,
            name=row.name,
            description=row.description,
            permissions=tuple(
                Permission(id=p.id, name=p.name, description=p.description)
                for p in row.permissions
            ),
        )


class SQLAlchemyPermissionRepository(PermissionRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, name: str, description: str = "") -> Permission:
        row = AuthPermission(name=name, description=description)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return Permission(id=row.id, name=row.name, description=row.description)


class SQLAlchemyAuditEventRepository(AuditEventRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        event_type: str,
        subject_id: UUID | None = None,
        actor_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        row = AuthAuditEvent(
            event_type=event_type,
            subject_id=subject_id,
            actor_id=actor_id,
            metadata_payload="{}" if metadata is None else str(metadata),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return AuditEvent(
            id=row.id,
            event_type=row.event_type,
            subject_id=row.subject_id,
            actor_id=row.actor_id,
            metadata={"raw": row.metadata_payload},
            created_at=row.created_at,
        )

    def list(self, *, limit: int = 50) -> list[AuditEvent]:
        rows = (
            self.session.query(AuthAuditEvent)
            .order_by(AuthAuditEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            AuditEvent(
                id=row.id,
                event_type=row.event_type,
                subject_id=row.subject_id,
                actor_id=row.actor_id,
                metadata={"raw": row.metadata_payload},
                created_at=row.created_at,
            )
            for row in rows
        ]
