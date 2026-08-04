# Discovery Engine

The discovery engine is the reusable orchestration layer that future network
collectors will use.

## Flow

1. Build a `DiscoveryContext` for the target.
2. Resolve the pipeline from `DiscoveryRegistry`.
3. Select collectors from `CollectorRegistry` based on capability coverage.
4. Run collector health checks.
5. Discover downstream targets.
6. Collect raw data.
7. Normalize raw data into immutable snapshot entities.
8. Validate the snapshot.
9. Persist the snapshot through the repository interface.

## Design Principles

- No vendor-specific logic lives in the framework.
- Collectors are abstract SDK components only.
- Discovery contexts stay separate from collector execution contexts.
- Snapshot persistence is interface-driven and pluggable.
- Validation happens before repository persistence.

## Key Types

- `CollectorCapability` defines the reusable capability vocabulary.
- `DiscoveryTarget` identifies a network endpoint without vendor assumptions.
- `DiscoveryContext` carries run metadata and capability requirements.
- `DiscoveryPipeline` coordinates collection, normalization, validation, and
  snapshot persistence.
- `DiscoveryEngine` resolves pipelines and executes discovery runs.
- `DiscoveryScheduler` runs discovery across multiple contexts.

