# Project Structure

## `backend/app/core`

- `application.py` FastAPI application factory and runtime container
- `constants.py` application-wide constants
- `exceptions.py` application exception hierarchy
- `lifecycle.py` startup and shutdown orchestration
- `metadata.py` immutable application metadata
- `plugins.py` in-memory plugin registry
- `dependencies.py` backward-compatible dependency exports

## `backend/app/domain`

- `entities.py` domain entity base class
- `interfaces.py` domain protocols
- `value_objects.py` immutable value object base class

## `backend/app/models`

- `base.py` SQLAlchemy declarative base
- `mixins.py` UUID, timestamp, and representation mixins

## `backend/app/repositories`

- `interfaces.py` generic repository protocol
- `sqlalchemy.py` SQLAlchemy repository base
- `transaction.py` transaction manager protocol
- `unit_of_work.py` SQLAlchemy unit-of-work implementation

## `backend/app/services`

- `base.py` base service and dependency context
- `utils.py` reusable service helpers

## `backend/app/events`

- `models.py` internal event definitions
- `interfaces.py` event publisher protocol
- `registry.py` handler registration
- `dispatcher.py` event dispatcher

## `backend/app/dependencies`

- `application.py` request-scoped application container access
- `database.py` database session dependency
- `settings.py` application settings dependency

