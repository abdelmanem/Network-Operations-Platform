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

## `backend/app/comparison`

- `__init__.py` NetBox comparison engine exports
- `engine.py` comparison pipeline orchestration
- `matcher.py` canonical NetBox-to-live inventory matching
- `comparator.py` device, interface, VLAN, platform, identity, and neighbor comparators
- `diff.py` immutable difference model and difference type enum
- `registry.py` difference registry and builder helpers
- `filters.py` difference filtering support
- `result.py` comparison result and metrics models
- `evidence.py` compliance evidence generation

## `backend/app/persistence`

- `__init__.py` immutable persistence exports
- `models.py` SQLAlchemy discovery history, snapshot, comparison, finding, and evidence models
- `repositories.py` history, snapshot, and finding repositories
- `unit_of_work.py` persistence unit-of-work integration
- `migrations.py` Alembic metadata imports

## `backend/app/history`

- `__init__.py` history query exports
- `discovery.py` discovery run history queries
- `snapshots.py` snapshot history queries
- `findings.py` finding history queries
- `timeline.py` chronological history timeline queries

## `backend/app/evaluation`

- `__init__.py` compliance evaluation engine exports
- `engine.py` evaluation orchestration and decision building
- `executor.py` executable rule type evaluation
- `policy.py` site, role, and platform policy scoping
- `registry.py` executable evaluation rule registry
- `context.py` evaluation context, exception, status, and decision models
- `scoring.py` risk and compliance score calculators
- `exceptions.py` evaluation exception hierarchy
- `remediation.py` remediation recommendation builder
- `metrics.py` evaluation metrics exports

## `backend/app/orchestration`

- `__init__.py` orchestration exports
- `engine.py` top-level orchestration job runner
- `workflow.py` end-to-end workflow executor
- `coordinator.py` collector runtime coordination and live snapshot aggregation
- `context.py` run context, cancellation token, and progress callback types
- `jobs.py` orchestration job model
- `state.py` run state machine
- `progress.py` immutable progress update model
- `events.py` orchestration event helpers
- `metrics.py` execution metrics tracking
- `results.py` immutable run result aggregation

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

## `backend/app/collectors/cisco`

- `__init__.py` Cisco inventory collector exports
- `base.py` shared Cisco inventory collection workflow and transport selection
- `ios.py` Catalyst IOS/IOS XE inventory collector
- `ce500.py` Catalyst Express 500 inventory collector
- `aironet.py` Aironet inventory collector
- `factory.py` Cisco collector factory and registry builder
- `inventory.py` Cisco inventory parser for SSH, SNMP, and HTTP payloads

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
- `diagnostics.py` transport diagnostic models
- `manager.py` transport orchestration
- `metrics.py` transport session metrics models
- `rate_limiter.py` token bucket rate limiting
- `registry.py` transport registry
- `retry.py` retry policy and backoff support
- `session.py` transport session lifecycle base class
- `timeout.py` timeout configuration model

## `backend/app/transports/ssh`

- `base.py` abstract SSH transport base class
- `netmiko.py` concrete Netmiko SSH transport
- `paramiko.py` concrete Paramiko SSH transport
- `session.py` abstract SSH session base class

## `backend/app/transports/snmp`

- `base.py` abstract SNMP transport base class
- `pysnmp.py` concrete pysnmp transport
- `session.py` abstract SNMP session base class

## `backend/app/transports/http`

- `base.py` abstract HTTP transport base class
- `httpx.py` concrete HTTPX transport
- `session.py` abstract HTTP session base class

## `backend/app/vendors`

- `cisco/__init__.py` Cisco platform support framework exports
- `cisco/capabilities.py` Cisco capability model and capability matrix
- `cisco/detection.py` Cisco platform detection signals
- `cisco/metadata.py` immutable Cisco platform metadata and definitions
- `cisco/platforms.py` Cisco platform registry
- `cisco/catalog/commands.py` Cisco command catalog definitions
- `cisco/catalog/snmp.py` Cisco SNMP OID catalog definitions
- `cisco/catalog/http.py` Cisco HTTP endpoint catalog definitions
- `cisco/models/ios.py` Cisco IOS platform definitions
- `cisco/models/iosxe.py` Cisco IOS XE platform definitions
- `cisco/models/aironet.py` Cisco Aironet platform definitions
- `cisco/models/ce500.py` Cisco Catalyst Express 500 platform definitions

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

## `backend/app/compliance`

- `__init__.py` compliance domain exports
- `domain/entities.py` immutable compliance entity base class
- `domain/enums.py` domain-wide compliance enums
- `domain/value_objects.py` immutable compliance value object base class
- `comparison/models.py` comparison target and metrics models
- `comparison/result.py` comparison result model
- `findings/evidence.py` immutable evidence model
- `findings/models.py` finding and recommendation models
- `findings/severity.py` severity level and severity value object
- `policies/models.py` policy and baseline models
- `rules/base.py` immutable rule model
- `rules/metadata.py` rule metadata model
- `rules/registry.py` rule registry

## `backend/app/collectors/execution`

- `exceptions.py` collector execution exception hierarchy
- `progress.py` execution progress model
- `result.py` collector execution result model
- `status.py` execution status enum

## `backend/app/collectors/runtime`

- `context.py` collector runtime context
- `dispatcher.py` runtime job dispatcher
- `engine.py` runtime orchestration engine
- `executor.py` collector execution executor
- `job.py` runtime job and queue primitives
- `lifecycle.py` runtime lifecycle hooks
- `metrics.py` runtime metrics tracking
- `scheduler.py` runtime scheduler
- `state.py` execution state machine

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

## `backend/app/api`

- `router.py` top-level API router composition
- `v1/` versioned FastAPI routes for health, metrics, jobs, history, findings, devices, comparison, and compliance
- `v1/dependencies.py` shared dependency injection helpers for application state and database access

## `backend/app/schemas`

- `common.py` shared pagination and error response models
- `jobs.py` job submission and status response models
- `discovery.py` discovery history response models
- `findings.py` finding and evidence response models
- `history.py` device history response models
- `devices.py` device history payload models
- `comparison.py` comparison result response models
- `compliance.py` compliance result response models
