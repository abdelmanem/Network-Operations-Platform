# Immutable Persistence

Milestone 13 introduces immutable PostgreSQL persistence for historical discovery
data. The persistence layer records what happened; it does not change collection,
comparison, reporting, or compliance scoring behavior.

## Persisted Records

- `discovery_runs`
- `snapshots`
- `snapshot_devices`
- `snapshot_interfaces`
- `snapshot_vlans`
- `snapshot_neighbors`
- `comparison_results`
- `findings`
- `evidence`

## Relationships

- A discovery run can own live snapshots.
- A comparison result references one expected NetBox snapshot and one observed
  live snapshot.
- Findings reference comparison results.
- Evidence references findings.

## Immutability

History rows are append-only. SQLAlchemy model events prevent updates and
deletes after records are inserted. New discovery runs, snapshots, comparison
results, findings, and evidence are inserted as new rows instead of replacing
prior data.

## Repositories

- `HistoryRepository` creates discovery runs and reads timelines.
- `SnapshotRepository` persists canonical NetBox snapshots and live snapshot
  entities.
- `FindingRepository` persists comparison results with generated findings and
  evidence.
- `PersistenceUnitOfWork` exposes those repositories behind one transaction
  boundary.

## Migration

Alembic revision `20260805_1300` creates all immutable history tables, foreign
keys, and lookup indexes for snapshot devices, VLANs, findings, evidence, and
comparison snapshot references.

## Performance Considerations

- Snapshot children are normalized into device, interface, VLAN, and neighbor
  tables for indexed history queries.
- Full snapshot payloads are also stored in JSON for audit reconstruction.
- Indexes are added on snapshot references, device identity fields, VLAN IDs,
  comparison snapshot references, finding references, and evidence references.

## Out of Scope

- Compliance scoring
- Report generation
- REST API endpoints
- Web UI
- Scheduling
