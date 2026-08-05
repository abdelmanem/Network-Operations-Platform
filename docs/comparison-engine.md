# NetBox Comparison Engine

Milestone 12 introduces the first business-value component in Network
Operations Platform: comparison of NetBox source-of-truth inventory against live
canonical snapshots.

## Scope

The comparison engine accepts:

- canonical NetBox inventory from `backend/app/inventory/dto.py`
- live canonical snapshots from `backend/app/snapshot/entities.py`

It emits:

- immutable inventory differences
- compliance findings
- evidence records
- comparison metrics

The engine does not persist data, modify NetBox, calculate compliance scores,
generate reports, or expose UI/API endpoints.

## Difference Types

Supported difference types are:

- `missing`
- `unexpected`
- `modified`
- `conflict`
- `duplicate`
- `unsupported`
- `unknown`

Every difference is converted into a `Finding` from the compliance domain model.

## Pipeline

1. `InventoryMatcher` matches NetBox devices to live device snapshots by name,
   then serial number.
2. `IdentityComparator` detects duplicate identities.
3. `DeviceComparator` compares core device attributes.
4. `InterfaceComparator` compares interface inventory.
5. `VLANComparator` compares VLAN inventory.
6. `NeighborComparator` records unsupported neighbor comparison evidence until
   NetBox neighbor inventory is modeled canonically.
7. `PlatformComparator` compares platform expectations.
8. `EvidenceGenerator` creates evidence for each difference.
9. `ComparisonEngine` converts differences into compliance findings and metrics.

## Design Decisions

- NetBox remains authoritative; live snapshot data is always treated as observed
  state.
- The comparison engine is framework-agnostic and contains no database, API, or
  reporting code.
- Findings are generated immediately because later milestones can reuse the
  compliance domain without translating drift again.
- Unsupported neighbor differences are explicit instead of silently ignored, so
  missing canonical NetBox relationship support remains visible.

## Performance Considerations

- Device, interface, and VLAN comparisons use dictionary indexes for stable
  linear-time matching.
- Difference registration deduplicates by stable keys.
- The current implementation is in-memory and suitable for the current device
  scale; larger deployments can add streaming/chunking without changing public
  comparison outputs.

## Testing

Tests include matcher coverage, registry behavior, filtered comparisons, fixture
data, and a golden difference-key test.
