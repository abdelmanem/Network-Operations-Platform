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
- `inventory.py` inventory synchronization service
- `utils.py` reusable service helpers

## `backend/app/discovery`

- `capabilities.py` collector capability definitions
- `context.py` discovery target and execution context
- `engine.py` discovery engine entrypoint
- `filters.py` reusable discovery filters
- `pipeline.py` discovery orchestration pipeline
- `registry.py` discovery pipeline registry
- `scheduler.py` discovery run scheduler
- `statistics.py` discovery metrics tracking

## `backend/app/collectors`

- `base.py` abstract collector SDK
- `capability.py` collector capability re-export
- `context.py` collector execution context
- `registry.py` collector registry
- `result.py` collector result model

## `backend/app/snapshot`

- `entities.py` immutable snapshot entities
- `mapper.py` entity-to-model conversion helpers
- `models.py` immutable Pydantic snapshot models
- `repository.py` snapshot repository protocol
- `serializer.py` JSON serialization helpers
- `validation.py` timestamp, identity, and version validation

## `backend/app/transports`

- `base.py` abstract transport interface and capability model
- `circuit_breaker.py` circuit breaker state machine
- `connection_pool.py` transport session pooling
- `credentials.py` credential resolution framework
- `manager.py` transport orchestration
- `rate_limiter.py` token bucket rate limiting
- `registry.py` transport registry
- `retry.py` retry policy and backoff support
- `session.py` transport session lifecycle base class
- `timeout.py` timeout configuration model

## `backend/app/transports/ssh`

- `base.py` abstract SSH transport base class
- `session.py` abstract SSH session base class

## `backend/app/transports/snmp`

- `base.py` abstract SNMP transport base class
- `session.py` abstract SNMP session base class

## `backend/app/transports/http`

- `base.py` abstract HTTP transport base class
- `session.py` abstract HTTP session base class

## `backend/app/parsers`

- `base.py` abstract parser interface
- `context.py` parser execution context and input formats
- `exceptions.py` parser exception hierarchy
- `pipeline.py` parser orchestration pipeline
- `registry.py` parser registry
- `result.py` structured parser output models

## `backend/app/normalization`

- `engine.py` normalization orchestration engine
- `mapper.py` parser-to-snapshot mapping helpers
- `registry.py` normalization rule registry
- `rules.py` normalization rule protocol
- `validator.py` normalization validation helpers

## `backend/app/cache`

- `redis.py` cache backends, fallback behavior, and cache decorators

## `backend/app/integrations/netbox`

- `authentication.py` token and OAuth-compatible auth strategies
- `cache.py` response cache keys and helpers
- `client.py` reusable NetBox REST client
- `endpoints.py` typed REST endpoint registry
- `exceptions.py` NetBox-specific exception hierarchy
- `mapper.py` transformation from NetBox payloads to canonical inventory models
- `models.py` typed NetBox payloads and collection responses
- `pagination.py` paginated list handling
- `retry.py` retry policy and backoff support
- `service.py` high-level NetBox integration service

## `backend/app/inventory`

- `dto.py` immutable inventory snapshot transfer object
- `entities.py` canonical inventory entities
- `mapper.py` mapping between NetBox payloads and canonical inventory snapshots
- `validation.py` payload, schema, and version validation

## `backend/app/events`

- `models.py` internal event definitions
- `interfaces.py` event publisher protocol
- `registry.py` handler registration
- `dispatcher.py` event dispatcher

## `backend/app/dependencies`

- `application.py` request-scoped application container access
- `database.py` database session dependency
- `settings.py` application settings dependency
