from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from backend.app.auth.application.services import (
    AuthenticationService,
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
from backend.app.database.session import SessionLocal, initialize_database

DEFAULT_ADMIN_ROLE_NAME = "admin"
MIN_PASSWORD_LENGTH = 8
DEFAULT_ADMIN_PERMISSIONS = (
    "credential:read",
    "credential:write",
    "discovery:target:read",
    "discovery:target:write",
    "discovery:job:submit",
    "discovery:job:read",
    "discovery:job:cancel",
    "discovery:evidence:read",
    "inventory:read",
    "inventory:write",
)


def _ensure_admin_permissions(session: Session, *, role_name: str) -> None:
    role_repo = SQLAlchemyRoleRepository(session)
    permission_repo = SQLAlchemyPermissionRepository(session)
    role = role_repo.get_by_name(role_name)
    if role is None:
        role = role_repo.create(name=role_name, description="Administrator role")

    for permission_name in DEFAULT_ADMIN_PERMISSIONS:
        permission = permission_repo.get_by_name(permission_name)
        if permission is None:
            permission = permission_repo.create(
                name=permission_name,
                description=f"Administrative access: {permission_name}",
            )
        role_repo.add_permission(role, permission)


def provision_admin_user(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
    confirm_password: str,
    role_name: str = DEFAULT_ADMIN_ROLE_NAME,
) -> User:
    """Create an administrator account using the existing auth architecture."""
    username = username.strip()
    email = email.strip()

    if not username:
        raise ValueError("Username is required")
    if not email or "@" not in email:
        raise ValueError("Valid email address is required")
    if not password:
        raise ValueError("Password is required")
    if password != confirm_password:
        raise ValueError("Password confirmation does not match")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    role_repo = SQLAlchemyRoleRepository(session)
    existing_role = role_repo.get_by_name(role_name)
    if existing_role is None:
        existing_role = role_repo.create(
            name=role_name,
            description="Administrator role",
        )
    _ensure_admin_permissions(session, role_name=role_name)
    existing_role = role_repo.get_by_name(role_name)

    user_repo = SQLAlchemyUserRepository(session)
    auth_service = AuthenticationService(
        user_repository=user_repo,
        role_repository=role_repo,
        permission_repository=SQLAlchemyPermissionRepository(session),
        audit_repository=SQLAlchemyAuditEventRepository(session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key=get_settings().auth_secret_key),
    )

    return auth_service.register_user(
        username=username,
        email=email,
        password=password,
        roles=[existing_role.name],
    )


def prompt_for_admin_identity() -> tuple[str, str, str, str]:
    username = input("Administrator username: ").strip()
    email = input("Administrator email: ").strip()
    password = getpass.getpass("Password: ")
    confirm_password = getpass.getpass("Confirm password: ")
    return username, email, password, confirm_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backend administration commands for Network Operations Platform"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = subparsers.add_parser(
        "create-admin",
        description="Create an initial administrator account",
    )
    create_admin_parser.add_argument(
        "--role",
        default=DEFAULT_ADMIN_ROLE_NAME,
        help="Role name to assign to the administrator",
    )

    args = parser.parse_args(argv)

    if args.command == "create-admin":
        initialize_database()
        session = SessionLocal()
        try:
            username, email, password, confirm_password = prompt_for_admin_identity()
            user = provision_admin_user(
                session,
                username=username,
                email=email,
                password=password,
                confirm_password=confirm_password,
                role_name=args.role,
            )
            print("Administrator account created successfully.")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Role: {args.role}")
            return 0
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        finally:
            session.close()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
