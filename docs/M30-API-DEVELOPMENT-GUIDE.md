# M30 API Development Guide: Missing Endpoints

**Purpose:** Concrete implementation guidance for 4 missing API endpoints needed for M30 frontend workflows  
**Scope:** Code locations, schemas, dependencies, test patterns  
**Effort:** Estimated 6-10 backend days + integration tests

---

## Quick Reference: Endpoints to Implement

| Endpoint | HTTP | Purpose | Priority | Complexity |
|---|---|---|---|---|
| GET /api/v1/inventory/netbox | GET | List all devices from latest NetBox snapshot | HIGH | Low |
| GET /api/v1/inventory/live | GET | List all discovered devices from latest live snapshot | HIGH | Low |
| GET /api/v1/devices/{device_id}/compare | GET | Side-by-side expected vs observed for single device | HIGH | Medium |
| GET /api/v1/snapshots/{snapshot_id}/... | GET (family) | Snapshot details (devices, interfaces, VLANs) | MEDIUM | Medium |

---

## Endpoint 1: GET /api/v1/inventory/netbox

### Purpose
Frontend needs to display "Expected Inventory" dashboard card showing all devices from NetBox.

### Where to Add
**File:** `backend/app/api/v1/inventory.py` (new file)

### Implementation Reference

```python
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.v1.dependencies import get_db_session
from backend.app.persistence.repositories import SnapshotRepository
from backend.app.schemas.inventory import InventoryListResponse, InventoryItemResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/inventory", tags=["inventory"])

class InventoryItemResponse(BaseModel):
    """Single device from inventory."""
    device_id: str
    name: str
    model: str | None = None
    serial_number: str | None = None
    platform: str | None = None
    primary_ip: str | None = None
    site: str | None = None
    role: str | None = None

class InventoryListResponse(BaseModel):
    """List of devices from inventory snapshot."""
    source: str  # "netbox" or "live"
    snapshot_id: UUID | None = None
    snapshot_captured_at: datetime | None = None
    device_count: int
    items: list[InventoryItemResponse]

@router.get("/netbox", response_model=InventoryListResponse, summary="List NetBox inventory")
async def list_netbox_inventory(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> InventoryListResponse:
    """List all devices from the latest NetBox snapshot."""
    
    repo = SnapshotRepository(db_session)
    snapshot = await repo.get_latest(source="netbox")
    
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No NetBox snapshot found. Run discovery first."
        )
    
    # Fetch all devices in this snapshot
    devices = await repo.get_snapshot_devices(snapshot_id=snapshot.id)
    
    items = [
        InventoryItemResponse(
            device_id=d.device_id,
            name=d.name,
            model=d.model,
            serial_number=d.serial_number,
            platform=d.platform,
            primary_ip=d.primary_ip,
            site=d.site,
            role=d.role,
        )
        for d in devices
    ]
    
    return InventoryListResponse(
        source="netbox",
        snapshot_id=snapshot.id,
        snapshot_captured_at=snapshot.captured_at,
        device_count=len(items),
        items=items
    )
```

### Where Data Comes From
- **Table:** `snapshots` + `snapshot_devices`
- **Query:** Latest snapshot where `source='netbox'`, then all devices with `snapshot_id=X`
- **Complexity:** Simple table join

### Test Pattern
```python
# tests/api/test_inventory.py
async def test_list_netbox_inventory_returns_devices():
    """Verify GET /inventory/netbox lists NetBox devices."""
    # Setup: Create a NetBox snapshot with devices
    snapshot = Snapshot(source="netbox", ...)
    device1 = SnapshotDevice(name="switch-01", ...)
    db_session.add(snapshot)
    db_session.add(device1)
    db_session.commit()
    
    # Execute
    response = await client.get("/api/v1/inventory/netbox")
    
    # Verify
    assert response.status_code == 200
    assert response.json()["device_count"] == 1
    assert response.json()["items"][0]["name"] == "switch-01"
```

### Wire Into Router
**File:** `backend/app/api/v1/router.py`
```python
from backend.app.api.v1.inventory import router as inventory_router

router = APIRouter(prefix="/api/v1")
router.include_router(inventory_router)
```

---

## Endpoint 2: GET /api/v1/inventory/live

### Purpose
Frontend needs to display "Live Inventory" dashboard card showing all devices discovered in last run.

### Implementation Reference
**Same as Endpoint 1, but with `source="live"`**

```python
@router.get("/live", response_model=InventoryListResponse, summary="List live inventory")
async def list_live_inventory(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> InventoryListResponse:
    """List all devices from the latest live discovery snapshot."""
    
    repo = SnapshotRepository(db_session)
    snapshot = await repo.get_latest(source="live")
    
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live snapshot found. Run discovery first."
        )
    
    devices = await repo.get_snapshot_devices(snapshot_id=snapshot.id)
    
    # Build response (same as above)
    ...
```

### Key Difference
- Query latest snapshot with `source="live"` instead of `"netbox"`
- Response will show last-discovered devices
- May be empty if no discovery has run yet

---

## Endpoint 3: GET /api/v1/devices/{device_id}/compare

### Purpose
Frontend needs single API call to get full expected vs observed state for a device. Currently requires multiple queries + client-side merging.

### Where to Add
**File:** `backend/app/api/v1/devices.py` (extend existing)

### Implementation Reference

```python
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/devices", tags=["devices"])

class ComparisonState(BaseModel):
    """Expected or observed state for a device."""
    device_id: str
    name: str | None = None
    model: str | None = None
    serial_number: str | None = None
    platform: str | None = None
    primary_ip: str | None = None
    site: str | None = None
    role: str | None = None
    # Add all fields from Snapshot schema

class VarianceSummary(BaseModel):
    """Summary of variances for a field."""
    field_name: str
    expected_value: object | None = None
    observed_value: object | None = None
    difference_type: str  # "MISSING", "UNEXPECTED", "MODIFIED"

class DeviceComparisonResponse(BaseModel):
    """Full comparison for a single device."""
    device_id: str
    expected_state: ComparisonState | None = None
    observed_state: ComparisonState | None = None
    variances: list[VarianceSummary] = Field(default_factory=list)
    comparison_result_id: UUID | None = None
    compared_at: datetime | None = None

@router.get("/{device_id}/compare", response_model=DeviceComparisonResponse, summary="Compare device")
async def compare_device(
    device_id: str,
    run_id: UUID | None = Query(None, description="Specific run to compare; latest if omitted"),
    db_session: Annotated[Session, Depends(get_db_session)],
) -> DeviceComparisonResponse:
    """Compare expected vs observed state for a single device."""
    
    from backend.app.persistence.repositories import (
        SnapshotRepository,
        FindingRepository,
    )
    
    snapshot_repo = SnapshotRepository(db_session)
    finding_repo = FindingRepository(db_session)
    
    # Get latest comparison run (or specific run_id)
    if run_id:
        comparison = await finding_repo.get_comparison_result(run_id)
    else:
        comparison = await finding_repo.get_latest_comparison_result()
    
    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No comparison found. Run discovery first."
        )
    
    # Get expected + observed snapshots
    expected_snapshot = await snapshot_repo.get(comparison.expected_snapshot_id)
    observed_snapshot = await snapshot_repo.get(comparison.observed_snapshot_id)
    
    # Get expected device
    expected_device = None
    if expected_snapshot:
        expected_device = await snapshot_repo.get_snapshot_device(
            snapshot_id=expected_snapshot.id,
            device_id=device_id
        )
    
    # Get observed device
    observed_device = None
    if observed_snapshot:
        observed_device = await snapshot_repo.get_snapshot_device(
            snapshot_id=observed_snapshot.id,
            device_id=device_id
        )
    
    # Get all findings for this device
    findings = await finding_repo.list_findings_by_device(device_id=device_id)
    
    # Build variances from findings
    variances = [
        VarianceSummary(
            field_name=f.expected_state.get("field_name", "unknown"),
            expected_value=f.expected_state.get("value"),
            observed_value=f.observed_state.get("value"),
            difference_type=f.expected_state.get("difference_type"),
        )
        for f in findings
    ]
    
    # Build response
    return DeviceComparisonResponse(
        device_id=device_id,
        expected_state=ComparisonState.from_snapshot_device(expected_device) if expected_device else None,
        observed_state=ComparisonState.from_snapshot_device(observed_device) if observed_device else None,
        variances=variances,
        comparison_result_id=comparison.id,
        compared_at=comparison.compared_at,
    )
```

### Where Data Comes From
- **Tables:** snapshots, snapshot_devices (expected), snapshot_devices (observed), findings, comparison_results
- **Query:** Get latest (or specific) comparison_result, fetch both snapshots, find all findings for device_id
- **Complexity:** Medium (multiple queries, needs careful joining)

### Test Pattern
```python
async def test_device_comparison_shows_expected_vs_observed():
    """Verify GET /devices/{id}/compare shows full comparison."""
    # Setup: Create comparison with expected + observed snapshots
    expected = Snapshot(source="netbox", ...)
    observed = Snapshot(source="live", ...)
    device_exp = SnapshotDevice(device_id="switch-01", model="Catalyst 3850", ...)
    device_obs = SnapshotDevice(device_id="switch-01", model="Catalyst 2950", ...)
    result = ComparisonResult(expected_snapshot_id=expected.id, ...)
    finding = Finding(difference_type="MODIFIED", ...)
    
    # Execute
    response = await client.get("/api/v1/devices/switch-01/compare")
    
    # Verify
    assert response.status_code == 200
    assert response.json()["expected_state"]["model"] == "Catalyst 3850"
    assert response.json()["observed_state"]["model"] == "Catalyst 2950"
    assert len(response.json()["variances"]) > 0
```

### Why This Matters for Frontend
- Single call instead of 3+ queries
- Operator clicks device → sees everything in one view
- No client-side merging logic needed

---

## Endpoint 4: GET /api/v1/snapshots/{snapshot_id}/...

### Purpose
Frontend needs to drill down into a snapshot to see devices, interfaces, VLANs. Also needed for evidence tracing.

### Family of Endpoints

#### 4a: GET /api/v1/snapshots/{snapshot_id}

```python
class SnapshotResponse(BaseModel):
    """Snapshot metadata and summary."""
    id: UUID
    source: str  # "netbox" or "live"
    device_count: int
    interface_count: int
    vlan_count: int
    captured_at: datetime
    metadata: dict[str, object] = {}

@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(
    snapshot_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> SnapshotResponse:
    """Get snapshot metadata."""
    repo = SnapshotRepository(db_session)
    snapshot = await repo.get(snapshot_id)
    
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    devices = await repo.get_snapshot_devices(snapshot_id)
    interfaces = await repo.get_snapshot_interfaces(snapshot_id)
    vlans = await repo.get_snapshot_vlans(snapshot_id)
    
    return SnapshotResponse(
        id=snapshot.id,
        source=snapshot.source,
        device_count=len(devices),
        interface_count=len(interfaces),
        vlan_count=len(vlans),
        captured_at=snapshot.captured_at,
    )
```

#### 4b: GET /api/v1/snapshots/{snapshot_id}/devices

```python
@router.get("/{snapshot_id}/devices", response_model=SnapshotDeviceListResponse)
async def get_snapshot_devices(
    snapshot_id: UUID,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> SnapshotDeviceListResponse:
    """Get all devices in snapshot."""
    repo = SnapshotRepository(db_session)
    devices = await repo.get_snapshot_devices(snapshot_id)
    
    items = [
        InventoryItemResponse.from_snapshot_device(d)
        for d in devices
    ]
    
    return SnapshotDeviceListResponse(
        snapshot_id=snapshot_id,
        device_count=len(items),
        items=items
    )
```

#### 4c: GET /api/v1/snapshots/{snapshot_id}/devices/{device_id}/interfaces

```python
class InterfaceResponse(BaseModel):
    interface_id: str
    name: str
    admin_status: str | None = None
    oper_status: str | None = None
    description: str | None = None
    mac_address: str | None = None
    speed: str | None = None

@router.get("/{snapshot_id}/devices/{device_id}/interfaces", response_model=InterfaceListResponse)
async def get_device_interfaces(
    snapshot_id: UUID,
    device_id: str,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> InterfaceListResponse:
    """Get all interfaces for device in snapshot."""
    repo = SnapshotRepository(db_session)
    interfaces = await repo.get_snapshot_interfaces(
        snapshot_id=snapshot_id,
        device_id=device_id
    )
    
    items = [InterfaceResponse.from_db(i) for i in interfaces]
    
    return InterfaceListResponse(
        snapshot_id=snapshot_id,
        device_id=device_id,
        interface_count=len(items),
        items=items
    )
```

#### 4d: GET /api/v1/snapshots/{snapshot_id}/devices/{device_id}/vlans

```python
class VlanResponse(BaseModel):
    vlan_id: int
    name: str
    status: str | None = None
    description: str | None = None

@router.get("/{snapshot_id}/devices/{device_id}/vlans", response_model=VlanListResponse)
async def get_device_vlans(
    snapshot_id: UUID,
    device_id: str,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> VlanListResponse:
    """Get all VLANs for device in snapshot."""
    # Similar to interfaces above
    ...
```

### Where Data Comes From
- **Tables:** snapshot_devices, snapshot_interfaces, snapshot_vlans, snapshot_neighbors
- **Query:** Filter by snapshot_id, then by device_id
- **Complexity:** Low-medium (straightforward filtering)

### Test Pattern
```python
async def test_get_snapshot_devices():
    """Verify GET /snapshots/{id}/devices lists devices."""
    # Setup
    snapshot = Snapshot(...)
    device = SnapshotDevice(snapshot_id=snapshot.id, ...)
    db_session.add(snapshot)
    db_session.add(device)
    db_session.commit()
    
    # Execute
    response = await client.get(f"/api/v1/snapshots/{snapshot.id}/devices")
    
    # Verify
    assert response.status_code == 200
    assert response.json()["device_count"] == 1
```

---

## Implementation Checklist

### Backend (APIs)

- [ ] Create `backend/app/api/v1/inventory.py`
  - [ ] InventoryListResponse schema
  - [ ] InventoryItemResponse schema
  - [ ] GET /inventory/netbox
  - [ ] GET /inventory/live

- [ ] Extend `backend/app/api/v1/devices.py`
  - [ ] ComparisonState schema
  - [ ] VarianceSummary schema
  - [ ] DeviceComparisonResponse schema
  - [ ] GET /devices/{device_id}/compare

- [ ] Create `backend/app/api/v1/snapshots.py`
  - [ ] SnapshotResponse schema
  - [ ] InterfaceResponse, VlanResponse, NeighborResponse schemas
  - [ ] List response schemas
  - [ ] GET /snapshots/{snapshot_id}
  - [ ] GET /snapshots/{snapshot_id}/devices
  - [ ] GET /snapshots/{snapshot_id}/devices/{device_id}/interfaces
  - [ ] GET /snapshots/{snapshot_id}/devices/{device_id}/vlans
  - [ ] GET /snapshots/{snapshot_id}/devices/{device_id}/neighbors

- [ ] Extend SnapshotRepository
  - [ ] Method: get_snapshot_devices(snapshot_id, device_id=None)
  - [ ] Method: get_snapshot_interfaces(snapshot_id, device_id=None)
  - [ ] Method: get_snapshot_vlans(snapshot_id, device_id=None)
  - [ ] Method: get_snapshot_neighbors(snapshot_id, device_id=None)

- [ ] Extend FindingRepository
  - [ ] Method: list_findings_by_device(device_id)
  - [ ] Method: get_latest_comparison_result()

- [ ] Wire into `backend/app/api/v1/router.py`

### Testing

- [ ] Integration tests for inventory endpoints
  - [ ] GET /inventory/netbox returns devices
  - [ ] GET /inventory/netbox 404 if no snapshot
  - [ ] GET /inventory/live returns devices
  - [ ] GET /inventory/live 404 if no snapshot

- [ ] Integration tests for device comparison
  - [ ] GET /devices/{id}/compare returns expected + observed
  - [ ] GET /devices/{id}/compare includes variances
  - [ ] GET /devices/{id}/compare 404 if no comparison

- [ ] Integration tests for snapshot details
  - [ ] GET /snapshots/{id} returns metadata
  - [ ] GET /snapshots/{id}/devices lists all devices
  - [ ] GET /snapshots/{id}/devices/{id}/interfaces lists interfaces
  - [ ] Same for VLANs and neighbors

### Deployment

- [ ] All endpoints typed (mypy ✅)
- [ ] All endpoints formatted (black ✅)
- [ ] All endpoints linted (ruff ✅)
- [ ] All tests passing (pytest ✅)
- [ ] CORS headers updated if needed
- [ ] Documentation in API docstrings

---

## Repository Methods to Add/Extend

### SnapshotRepository

```python
# Add these methods
async def get_snapshot_devices(
    self,
    snapshot_id: UUID,
    device_id: str | None = None,
) -> list[SnapshotDevice]:
    """Get all devices in snapshot, optionally filtered by device_id."""
    query = select(SnapshotDevice).filter(SnapshotDevice.snapshot_id == snapshot_id)
    if device_id:
        query = query.filter(SnapshotDevice.device_id == device_id)
    result = await self.session.execute(query)
    return result.scalars().all()

async def get_snapshot_interfaces(
    self,
    snapshot_id: UUID,
    device_id: str | None = None,
) -> list[SnapshotInterface]:
    """Get all interfaces in snapshot, optionally filtered by device."""
    query = select(SnapshotInterface).filter(SnapshotInterface.snapshot_id == snapshot_id)
    if device_id:
        query = query.filter(SnapshotInterface.device_id == device_id)
    result = await self.session.execute(query)
    return result.scalars().all()

# Same for VLANs and neighbors
```

### FindingRepository

```python
async def list_findings_by_device(
    self,
    device_id: str,
) -> list[Finding]:
    """Get all findings for a specific device."""
    query = select(Finding).filter(
        Finding.metadata["device_id"].astext == device_id
    )
    result = await self.session.execute(query)
    return result.scalars().all()

async def get_latest_comparison_result(self) -> ComparisonResult | None:
    """Get most recent comparison result."""
    query = select(ComparisonResult).order_by(
        ComparisonResult.compared_at.desc()
    ).limit(1)
    result = await self.session.execute(query)
    return result.scalars().first()
```

---

## Timeline Estimate

| Task | Days | Notes |
|---|---|---|
| Implement Endpoints 1-2 (inventory) | 1-2 | Simple, similar logic |
| Implement Endpoint 3 (device compare) | 2-3 | Requires careful joining |
| Implement Endpoint 4 (snapshot details) | 2-3 | Multiple sub-endpoints |
| Extend repositories | 1 | Add query methods |
| Integration tests | 2-3 | ~15 tests |
| Code review + fixes | 1-2 | Iteration |
| **Total** | **9-14** | **~2 weeks** |

---

## Success Criteria

- ✅ All 4+ endpoints implemented
- ✅ All integration tests passing
- ✅ Type checking passes (mypy)
- ✅ Formatting passes (black)
- ✅ Linting passes (ruff)
- ✅ Frontend can render inventory cards without workarounds
- ✅ Frontend can render device comparison without multiple API calls
- ✅ Frontend can drill down into interfaces/VLANs without custom queries

