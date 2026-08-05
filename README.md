# Network Operations Platform

Network Operations Platform is an enterprise framework for validating Cisco network
infrastructure against NetBox Community v4.6.7.

This repository currently contains the Sprint 1 foundation, the Milestone 2 core
framework, the Milestone 3 NetBox source-of-truth integration boundary, the
Milestone 4 discovery and snapshot framework, and the Milestone 5 reusable
transport framework, the Milestone 6 parser and normalization framework, and
the Milestone 7 compliance domain model, and the Milestone 8 collector runtime
framework:

- FastAPI application scaffold
- typed Pydantic Settings configuration
- SQLAlchemy 2 database layer
- Alembic migration environment
- structured JSON logging
- `/health` endpoint
- reusable core, domain, model, repository, service, event, and dependency layers
- NetBox integration client, cache, pagination, retry, and mapping layers
- canonical inventory domain models and inventory synchronization service
- discovery engine, collector SDK, and immutable snapshot framework
- reusable transport manager, registry, pooling, retries, and lifecycle support
- parser registry, parser pipeline, and normalization engine for canonical models
- immutable compliance rules, policies, findings, evidence, and comparison results
- collector runtime engine, scheduler, dispatcher, state machine, and metrics

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
- `backend/app/integrations/netbox/` NetBox REST client, endpoint registry, cache, pagination, and mapping
- `backend/app/cache/` cache adapters and decorators
- `backend/app/inventory/` canonical inventory entities, DTOs, mapping, and validation
- `backend/app/events/` event definitions, dispatcher, and registration
- `backend/app/dependencies/` dependency injection providers
- `backend/app/api/` API routing
- `backend/app/database/` SQLAlchemy setup
- `alembic/` database migration environment

## Milestone 2 Notes

Milestone 2 establishes the internal application framework only. It intentionally
does not implement NetBox integration, Cisco collectors, compliance rules, or
report generation.

Milestone 3 establishes the read-only NetBox integration boundary and canonical
inventory model. It intentionally does not communicate with Cisco devices, run
compliance logic, or persist inventory data.

Milestone 4 establishes the reusable discovery pipeline, collector registry,
collector capability model, and immutable snapshot framework. It intentionally
does not execute vendor-specific commands or connect to Cisco devices.

Milestone 5 establishes the reusable transport layer, including abstract
transport interfaces, session lifecycle management, connection pooling,
credentials, retries, circuit breaking, timeout handling, and rate limiting.
It intentionally does not execute vendor-specific commands or issue network
requests.

Milestone 6 establishes the parser and normalization framework that converts
raw transport output into canonical snapshot entities. It intentionally does not
execute vendor-specific commands, perform network access, or apply business
rules.

Milestone 7 establishes the reusable compliance domain model, including rules,
policies, findings, evidence, severity, and comparison results. It intentionally
does not execute evaluation logic, transport operations, or reporting.

Milestone 8 establishes the collector runtime framework, including scheduling,
dispatching, execution state tracking, cancellation, retry, timeout handling,
and runtime metrics. It intentionally does not implement vendor-specific
commands, transport logic, parsing rules, or compliance evaluation.

The detailed package map lives in `docs/project-structure.md`.
