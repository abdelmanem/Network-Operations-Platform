# Network Operations Platform

Network Operations Platform is an enterprise framework for validating Cisco network
infrastructure against NetBox Community v4.6.7.

This repository currently contains the Sprint 1 foundation and the Milestone 2 core framework:

- FastAPI application scaffold
- typed Pydantic Settings configuration
- SQLAlchemy 2 database layer
- Alembic migration environment
- structured JSON logging
- `/health` endpoint
- reusable core, domain, model, repository, service, event, and dependency layers

## Requirements

- Python 3.12
- PostgreSQL 16
- Redis 7

## Quick Start

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

3. Copy `.env.example` to `.env` and adjust values.
4. Run the application:

```bash
uvicorn backend.app.main:app --reload
```

5. Check health:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","version":"0.1.0"}
```

## Project Structure

- `backend/app/main.py` application entrypoint
- `backend/app/config/` application settings and logging
- `backend/app/core/` application lifecycle, metadata, exceptions, plugins, and factory
- `backend/app/domain/` domain entity and value object foundations
- `backend/app/models/` SQLAlchemy base model and common mixins
- `backend/app/repositories/` repository and unit-of-work abstractions
- `backend/app/services/` base service support and helpers
- `backend/app/events/` event definitions, dispatcher, and registration
- `backend/app/dependencies/` dependency injection providers
- `backend/app/api/` API routing
- `backend/app/database/` SQLAlchemy setup
- `alembic/` database migration environment

## Milestone 2 Notes

Milestone 2 establishes the internal application framework only. It intentionally
does not implement NetBox integration, Cisco collectors, compliance rules, or
report generation.

The detailed package map lives in `docs/project-structure.md`.
