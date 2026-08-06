from __future__ import annotations

from collections.abc import Generator

import pytest
from backend.app.collectors.runtime.context import CollectorRuntimeContext
from backend.app.core.application import create_application
from backend.app.models.base import BaseModel
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class FakeInventoryService:
    async def synchronize(self, *, force_refresh: bool = False) -> object:
        return object()


class FakeCollectorRuntime:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def submit(
        self, context: CollectorRuntimeContext, *, priority: int = 0
    ) -> object:
        return object()

    async def run_job(self, job: object) -> object:
        class Result:
            snapshot = None

        return Result()

    async def collect(
        self, contexts: tuple[CollectorRuntimeContext, ...]
    ) -> tuple[object, tuple[object, ...]]:
        return object(), ()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    BaseModel.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    with session_factory():
        app = create_application()
        app.state.container = type(
            "Container",
            (),
            {
                "settings": type("Settings", (), {"app_version": "0.1.0"})(),
                "metadata": type(
                    "Metadata", (), {"name": "test", "version": "0.1.0"}
                )(),
            },
        )()
        with TestClient(app) as test_client:
            yield test_client


def test_health_endpoint() -> None:
    with TestClient(create_application()) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_version_endpoint() -> None:
    with TestClient(create_application()) as client:
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        assert response.json()["version"] == "0.1.0"


def test_metrics_endpoint() -> None:
    with TestClient(create_application()) as client:
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        payload = response.json()
        assert payload["service"] == "network-operations-platform"


def test_job_submission_and_status() -> None:
    with TestClient(create_application()) as client:
        payload = {
            "collector_contexts": [
                {"target": {"identifier": "switch-01", "address": "10.0.0.1"}}
            ],
            "policies": [],
            "metadata": {"site": "HQ"},
        }
        response = client.post("/api/v1/jobs/discovery", json=payload)
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        job_id = body["job_id"]

        status_response = client.get(f"/api/v1/jobs/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["job_id"] == job_id
