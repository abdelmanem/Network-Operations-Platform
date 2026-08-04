# Transport Framework

The transport framework provides reusable infrastructure for all future
collectors.

## Goals

- Keep transport concerns separate from collector logic.
- Avoid vendor-specific code.
- Provide a consistent lifecycle for sessions, retries, and pooling.
- Support dependency injection and framework-agnostic composition.

## Core Pieces

- `TransportCapability` advertises reusable transport features.
- `TransportTarget` identifies the remote endpoint without vendor assumptions.
- `TransportContext` carries credentials, timeout, retry, and metadata values.
- `TransportRegistry` resolves transport implementations.
- `TransportManager` coordinates selection, pooling, and lifecycle operations.
- `ConnectionPool` reuses transport sessions.
- `TransportSession` provides the session lifecycle contract.
- `TransportRetryPolicy`, `CircuitBreaker`, `TransportTimeout`, and
  `RateLimiter` provide the reusable policy layer.

## Specializations

The `ssh`, `snmp`, and `http` subpackages define abstract base classes only.
They exist so future vendor-specific transports can extend a stable contract
without changing the public package layout.
