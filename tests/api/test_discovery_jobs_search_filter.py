from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from backend.app.api.v1.dependencies import get_db_session as get_db_v1
from backend.app.auth.api.dependencies import (
    get_auth_service as get_auth_service_dep,
    get_db_session as get_db_auth,
)
from backend.app.auth.application.services import (
    AuthenticationService,
    PasswordHashingService,
    TokenService,
)
from backend.app.auth.infrastructure.repositories import (
    SQLAlchemyAuditEventRepository,
    SQLAlchemyPermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemyUserRepository,
)
from backend.app.cli import provision_admin_user
from backend.app.core.application import create_application
from backend.app.models.base import BaseModel
from backend.app.persistence.discovery_repositories import (
    DiscoveryJobRepository,
    DiscoveryTargetRepository,
)
from backend.app.persistence.models import (
    DiscoveryJobRecord,
    DiscoveryRunRecord,
    DiscoveryTargetRecord,
)
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _build_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    BaseModel.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)()


def _setup_app_and_client(
    session: Session,
) -> tuple[TestClient, dict[str, str], AuthenticationService]:
    app = create_application()

    auth_service = AuthenticationService(
        user_repository=SQLAlchemyUserRepository(session),
        role_repository=SQLAlchemyRoleRepository(session),
        permission_repository=SQLAlchemyPermissionRepository(session),
        audit_repository=SQLAlchemyAuditEventRepository(session),
        password_service=PasswordHashingService(),
        token_service=TokenService(secret_key="test-secret"),
    )

    def override_get_db_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db_v1] = override_get_db_session
    app.dependency_overrides[get_db_auth] = override_get_db_session
    app.dependency_overrides[get_auth_service_dep] = lambda: auth_service

    provision_admin_user(
        session,
        username="admin_user",
        email="admin@example.com",
        password="StrongPass1!",
        confirm_password="StrongPass1!",
        role_name="admin",
    )

    token_pair = auth_service.authenticate_user("admin_user", "StrongPass1!")
    headers = {
        "Authorization": f"Bearer {token_pair.access_token}",
        "X-Tenant-ID": "tenant-a",
    }

    return TestClient(app), headers, auth_service


def _seed_test_jobs(session: Session, tenant_id: str = "tenant-a") -> dict[str, Any]:
    target_repo = DiscoveryTargetRepository(session)
    t1 = target_repo.create(
        tenant_id=tenant_id,
        identifier="cisco-core-sw",
        address="192.168.20.0/24",
        scope_type="cidr_network",
        scope_cidr="192.168.20.0/24",
        credential_reference="secret-ref-1",
    )
    t2 = target_repo.create(
        tenant_id=tenant_id,
        identifier="arista-leaf-01",
        address="10.10.0.1",
        scope_type="single_device",
        credential_reference="secret-ref-2",
    )
    t3 = target_repo.create(
        tenant_id=tenant_id,
        identifier="juniper-edge-01",
        address="172.16.0.1",
        scope_type="single_device",
        credential_reference="secret-ref-3",
    )

    now = datetime.now(UTC)
    run1 = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_identifier=t1.identifier,
        target_address=t1.address,
        status="completed",
    )
    run2 = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_identifier=t2.identifier,
        target_address=t2.address,
        status="failed",
    )
    run3 = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_identifier=t1.identifier,
        target_address=t1.address,
        status="started",
    )
    run4 = DiscoveryRunRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_identifier=t3.identifier,
        target_address=t3.address,
        status="queued",
    )
    session.add_all([run1, run2, run3, run4])
    session.flush()

    job_queued = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_id=t3.id,
        run_id=run4.id,
        state="queued",
        requested_at=now - timedelta(days=2),
        started_at=None,
        completed_at=None,
    )
    job_running = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_id=t1.id,
        run_id=run3.id,
        state="running",
        requested_at=now - timedelta(hours=5),
        started_at=now - timedelta(hours=5),
        completed_at=None,
        execution_owner=uuid4(),
        lease_expires_at=now + timedelta(minutes=5),
        last_heartbeat_at=now - timedelta(seconds=10),
    )
    job_succeeded = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_id=t1.id,
        run_id=run1.id,
        state="succeeded",
        requested_at=now - timedelta(days=1),
        started_at=now - timedelta(days=1),
        completed_at=now - timedelta(days=1) + timedelta(minutes=2),
    )
    job_failed = DiscoveryJobRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        target_id=t2.id,
        run_id=run2.id,
        state="failed",
        failure_code="TRANSPORT_UNAVAILABLE",
        failure_message="TCP connection to 10.10.0.1 timed out.",
        requested_at=now - timedelta(minutes=30),
        started_at=now - timedelta(minutes=30),
        completed_at=now - timedelta(minutes=28),
    )
    session.add_all([job_queued, job_running, job_succeeded, job_failed])
    session.commit()

    return {
        "target1": t1,
        "target2": t2,
        "target3": t3,
        "job_queued": job_queued,
        "job_running": job_running,
        "job_succeeded": job_succeeded,
        "job_failed": job_failed,
        "run1": run1,
        "run2": run2,
        "run3": run3,
        "run4": run4,
    }


def test_default_job_listing_with_pagination() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        _seed_test_jobs(session)

        response = client.get("/api/v1/discovery/jobs", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4
        assert data["page"] == 1
        assert data["total_pages"] == 1
        assert not data["has_next"]

        # Check enriched target fields
        item = data["items"][0]
        assert "target_identifier" in item
        assert "target_address" in item
    finally:
        session.close()


def test_search_by_job_id() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        data_map = _seed_test_jobs(session)
        target_job = data_map["job_failed"]
        partial_id = str(target_job.id)[:8]

        response = client.get(f"/api/v1/discovery/jobs?q={partial_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["job_id"] == str(target_job.id)
    finally:
        session.close()


def test_search_by_run_id() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        data_map = _seed_test_jobs(session)
        run2 = data_map["run2"]
        partial_run_id = str(run2.id)[:8]

        response = client.get(f"/api/v1/discovery/jobs?q={partial_run_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["discovery_run_id"] == str(run2.id)
    finally:
        session.close()


def test_search_by_target_identifier_and_address() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        _seed_test_jobs(session)

        # Search by target identifier
        response = client.get("/api/v1/discovery/jobs?q=arista", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["target_identifier"] == "arista-leaf-01"

        # Search by target address
        response2 = client.get("/api/v1/discovery/jobs?q=192.168.20", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["total"] == 2
    finally:
        session.close()


def test_search_by_failure_code_and_message() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        _seed_test_jobs(session)

        # Search by failure code
        response = client.get("/api/v1/discovery/jobs?q=TRANSPORT_UNAVAILABLE", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["error_code"] == "TRANSPORT_UNAVAILABLE"

        # Search by message snippet
        response2 = client.get("/api/v1/discovery/jobs?q=timed+out", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["total"] == 1
    finally:
        session.close()


def test_status_filter() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        _seed_test_jobs(session)

        # Running status
        response = client.get("/api/v1/discovery/jobs?status=running", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "running"

        # Succeeded status
        response2 = client.get("/api/v1/discovery/jobs?status=succeeded", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["total"] == 1

        # Cancelled status (none in seed)
        response3 = client.get("/api/v1/discovery/jobs?status=cancelled", headers=headers)
        assert response3.status_code == status.HTTP_200_OK
        assert response3.json()["total"] == 0
    finally:
        session.close()


def test_target_filter() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        data_map = _seed_test_jobs(session)
        t2 = data_map["target2"]

        response = client.get(f"/api/v1/discovery/jobs?target_id={t2.id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["target_id"] == str(t2.id)
    finally:
        session.close()


def test_date_range_filtering() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        _seed_test_jobs(session)
        now = datetime.now(UTC)

        # Filter last 2 hours (should only match job_failed requested 30m ago)
        date_from = (now - timedelta(hours=2)).isoformat()
        response = client.get(
            "/api/v1/discovery/jobs",
            params={"date_from": date_from},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "failed"
    finally:
        session.close()


def test_sorting_options() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        _seed_test_jobs(session)

        # Sort oldest first
        response_oldest = client.get("/api/v1/discovery/jobs?sort=oldest", headers=headers)
        assert response_oldest.status_code == status.HTTP_200_OK
        assert response_oldest.json()["items"][0]["status"] == "queued"

        # Sort recently started
        response_started = client.get("/api/v1/discovery/jobs?sort=recently_started", headers=headers)
        assert response_started.status_code == status.HTTP_200_OK
        # Most recently started is job_failed (started 30m ago)
        assert response_started.json()["items"][0]["status"] == "failed"

        # Sort longest running
        response_duration = client.get("/api/v1/discovery/jobs?sort=longest_running", headers=headers)
        assert response_duration.status_code == status.HTTP_200_OK
        # The running job has been active for 5 hours
        assert response_duration.json()["items"][0]["status"] == "running"

        # Sort target A-Z
        response_target = client.get("/api/v1/discovery/jobs?sort=target&order=asc", headers=headers)
        assert response_target.status_code == status.HTTP_200_OK
        assert response_target.json()["items"][0]["target_identifier"] == "arista-leaf-01"
    finally:
        session.close()


def test_unsupported_sort_value_is_rejected() -> None:
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        _seed_test_jobs(session)

        response = client.get("/api/v1/discovery/jobs?sort=malicious_sql_column", headers=headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Unsupported sort field" in response.json()["detail"]
    finally:
        session.close()


def test_tenant_isolation_in_jobs_search_and_filter() -> None:
    session = _build_test_session()
    try:
        client, headers_a, _ = _setup_app_and_client(session)
        _seed_test_jobs(session, tenant_id="tenant-a")
        _seed_test_jobs(session, tenant_id="tenant-b")

        # Tenant A request only sees tenant-a jobs
        response_a = client.get("/api/v1/discovery/jobs", headers=headers_a)
        assert response_a.status_code == status.HTTP_200_OK
        assert response_a.json()["total"] == 4
        for item in response_a.json()["items"]:
            assert item["tenant_id"] == "tenant-a"

        # Search across tenant A does not return tenant B results
        headers_b = dict(headers_a, **{"X-Tenant-ID": "tenant-b"})
        response_b = client.get("/api/v1/discovery/jobs?q=cisco", headers=headers_b)
        assert response_b.status_code == status.HTTP_200_OK
        for item in response_b.json()["items"]:
            assert item["tenant_id"] == "tenant-b"
    finally:
        session.close()


def test_orphaned_job_regression_search_scenario() -> None:
    """Regression test representing the real-world orphaned job scenario.

    Job: 9098a446-a652-4b0a-8a01-2eed4846957b
    Run: 9914db93-3b3a-49b0-a9ca-3ffe57f377e1
    Target: 5a258795-31a5-475d-8d00-1a25c93c8ac3 (cisco / 192.168.20.0/24)
    """
    session = _build_test_session()
    try:
        client, headers, _ = _setup_app_and_client(session)
        target_id = UUID("5a258795-31a5-475d-8d00-1a25c93c8ac3")
        job_id = UUID("9098a446-a652-4b0a-8a01-2eed4846957b")
        run_id = UUID("9914db93-3b3a-49b0-a9ca-3ffe57f377e1")

        target = DiscoveryTargetRecord(
            id=target_id,
            tenant_id="tenant-a",
            identifier="cisco",
            address="192.168.20.0/24",
            scope_type="cidr_network",
            scope_cidr="192.168.20.0/24",
            credential_reference="secret-ref-cisco",
        )
        run = DiscoveryRunRecord(
            id=run_id,
            tenant_id="tenant-a",
            target_identifier="cisco",
            target_address="192.168.20.0/24",
            status="started",
        )
        job = DiscoveryJobRecord(
            id=job_id,
            tenant_id="tenant-a",
            target_id=target_id,
            run_id=run_id,
            state="running",
            failure_code="EXECUTION_TIMEOUT",
            failure_message="Stale execution orphaned without active lease",
            requested_at=datetime(2026, 8, 22, 19, 59, 47, tzinfo=UTC),
            started_at=datetime(2026, 8, 22, 19, 59, 47, tzinfo=UTC),
            execution_owner=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
        )
        session.add_all([target, run, job])
        session.commit()

        # Locate by job ID prefix
        r1 = client.get("/api/v1/discovery/jobs?q=9098a446", headers=headers)
        assert r1.status_code == status.HTTP_200_OK
        assert r1.json()["total"] == 1
        assert r1.json()["items"][0]["job_id"] == str(job_id)

        # Locate by run ID prefix
        r2 = client.get("/api/v1/discovery/jobs?q=9914db93", headers=headers)
        assert r2.status_code == status.HTTP_200_OK
        assert r2.json()["total"] == 1

        # Locate by target identifier
        r3 = client.get("/api/v1/discovery/jobs?q=cisco", headers=headers)
        assert r3.status_code == status.HTTP_200_OK
        assert r3.json()["total"] == 1

        # Locate by target address
        r4 = client.get("/api/v1/discovery/jobs?q=192.168.20.0/24", headers=headers)
        assert r4.status_code == status.HTTP_200_OK
        assert r4.json()["total"] == 1

        # Locate by failure code
        r5 = client.get("/api/v1/discovery/jobs?q=EXECUTION_TIMEOUT", headers=headers)
        assert r5.status_code == status.HTTP_200_OK
        assert r5.json()["total"] == 1
    finally:
        session.close()
