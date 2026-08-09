from __future__ import annotations

from backend.app.auth.application.services import PasswordHashingService
from backend.app.auth.infrastructure.models import BaseModel
from backend.app.auth.infrastructure.repositories import SQLAlchemyRoleRepository
from backend.app.cli import provision_admin_user
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

TEST_PASSWORD = "StrongPass1!"
TEST_PASSWORD_ALT = "StrongPass2!"
TEST_SHORT_PASSWORD = "short"


def _build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    BaseModel.metadata.create_all(engine)
    return Session(engine)


def test_provision_admin_user_creates_an_admin_account() -> None:
    session = _build_session()
    try:
        user = provision_admin_user(
            session,
            username="admin",
            email="admin@example.com",
            password=TEST_PASSWORD,
            confirm_password=TEST_PASSWORD,
            role_name="admin",
        )

        assert user.username == "admin"
        assert user.email == "admin@example.com"
        assert any(role.name == "admin" for role in user.roles)
    finally:
        session.close()


def test_provision_admin_user_hashes_password() -> None:
    session = _build_session()
    try:
        user = provision_admin_user(
            session,
            username="hashuser",
            email="hashuser@example.com",
            password=TEST_PASSWORD,
            confirm_password=TEST_PASSWORD,
            role_name="admin",
        )

        password_service = PasswordHashingService()
        assert password_service.verify_password("StrongPass1!", user.password_hash)
        assert user.password_hash != "StrongPass1!"
    finally:
        session.close()


def test_provision_admin_user_requires_password_confirmation() -> None:
    session = _build_session()
    try:
        try:
            provision_admin_user(
                session,
                username="confirm",
                email="confirm@example.com",
                password=TEST_PASSWORD,
                confirm_password="DifferentPass1!",
                role_name="admin",
            )
        except ValueError as exc:
            assert "confirmation" in str(exc).lower()
        else:
            raise AssertionError("Expected password confirmation failure")
    finally:
        session.close()


def test_provision_admin_user_rejects_duplicate_user() -> None:
    session = _build_session()
    try:
        provision_admin_user(
            session,
            username="dupe",
            email="dupe@example.com",
            password=TEST_PASSWORD,
            confirm_password=TEST_PASSWORD,
            role_name="admin",
        )

        try:
            provision_admin_user(
                session,
                username="dupe",
                email="dupe2@example.com",
                password=TEST_PASSWORD_ALT,
                confirm_password=TEST_PASSWORD_ALT,
                role_name="admin",
            )
        except ValueError as exc:
            assert "already exists" in str(exc).lower()
        else:
            raise AssertionError("Expected duplicate user failure")
    finally:
        session.close()


def test_provision_admin_user_assigns_existing_admin_role() -> None:
    session = _build_session()
    try:
        role_repo = SQLAlchemyRoleRepository(session)
        role_repo.create(name="admin", description="Administrator")

        user = provision_admin_user(
            session,
            username="roleuser",
            email="roleuser@example.com",
            password="StrongPass1!",
            confirm_password="StrongPass1!",
            role_name="admin",
        )

        assert user.roles
        assert user.roles[0].name == "admin"
    finally:
        session.close()


def test_provision_admin_user_rejects_invalid_input() -> None:
    session = _build_session()
    try:
        for username, email, password, confirm in [
            ("", "admin@example.com", TEST_PASSWORD, TEST_PASSWORD),
            ("admin", "", TEST_PASSWORD, TEST_PASSWORD),
            ("admin", "admin@example.com", "", ""),
            ("admin", "admin@example.com", TEST_SHORT_PASSWORD, TEST_SHORT_PASSWORD),
        ]:
            try:
                provision_admin_user(
                    session,
                    username=username,
                    email=email,
                    password=password,
                    confirm_password=confirm,
                    role_name="admin",
                )
            except ValueError:
                continue
            raise AssertionError("Expected invalid input failure")
    finally:
        session.close()
