# Snapshot Model

The snapshot model is the immutable, vendor-agnostic representation of network
state produced by collectors and consumed by downstream modules.

## Core Entities

- `InventorySnapshot` is the root immutable snapshot.
- `DeviceSnapshot` captures device-level state.
- `InterfaceSnapshot` captures interface state.
- `VLANSnapshot` captures VLAN state.
- `MACTableSnapshot` captures MAC table state.
- `NeighborSnapshot` captures adjacency state.
- `PowerSnapshot` captures device power state.

## Characteristics

- Immutable by design.
- Independent of NetBox and all vendor APIs.
- Suitable for validation, serialization, and repository storage.
- Backed by Pydantic models for schema enforcement and serialization.

## Validation

- Timestamp values must be timezone-aware and not in the future.
- Device identifiers must be present.
- Snapshot schema versions must match the expected framework version.
- Device identities must be unique within a snapshot.

## Serialization

- `SnapshotSerializer` converts snapshot models to and from JSON bytes.
- `SnapshotMapper` converts between immutable entities and Pydantic models.

