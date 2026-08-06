# Policy Management Framework

This milestone introduces a reusable policy management subsystem designed for immutable policy definitions, deterministic inheritance, validation, compilation, and repository access.

## Core concepts

- Policy: immutable definition with key, name, version, lifecycle, metadata, rules, baselines, assignments, and inheritance.
- PolicyVersion: semantic versioning with history and previous-version tracking.
- PolicyLifecycle: Draft, Review, Approved, Published, Deprecated, Archived.
- PolicyAssignment: deterministic assignment targets for organization, site, building, floor, rack, vendor, platform, device type, and individual device scopes.
- PolicyCompiler: builds immutable evaluation packages from validated policies.
- PolicyValidator: validates duplicate rule references, inheritance cycles, baselines, versions, and assignments.
- InMemoryPolicyRepository: immutable repository that refuses modifications to published versions.

## Design decisions

- The policy model is immutable and uses frozen dataclasses.
- The compiler emits immutable evaluation packages consumed by downstream engines.
- Validation is framework-agnostic and reusable outside the REST layer.
- Repository operations are intentionally read-only for published policies.
