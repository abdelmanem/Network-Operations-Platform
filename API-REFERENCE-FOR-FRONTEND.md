# M29.5 Backend API Reference for Frontend

## Available Endpoints (Ready for M30)

### 1. Discovery History
**Endpoint:** `GET /history/discovery-runs`

**Query Parameters:**
- `page` (int, default=1): Page number for pagination
- `page_size` (int, default=20): Items per page (max 200)

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "target_identifier": "switch-01",
      "target_address": "10.0.0.1",
      "status": "succeeded|failed|started",
      "metadata": {"site": "HQ", "device_role": "access", "platform": "iosxe"},
      "created_at": "2026-08-15T09:30:00Z",
      "started_at": "2026-08-15T09:30:00Z",
      "finished_at": "2026-08-15T09:30:15Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 100,
  "has_next": true
}
```

**Frontend Use Case:** Show discovery run history timeline

---

### 2. Device History
**Endpoint:** `GET /devices/{device_id}/history`

**Query Parameters:**
- `page` (int, default=1): Pagination
- `page_size` (int, default=20): Items per page

**Response:**
```json
{
  "device_id": "switch-01",
  "items": [
    {
      "id": "uuid",
      "device_id": "switch-01",
      "name": "switch-01",
      "model": "WS-C2960X",
      "serial_number": "ABC123",
      "platform": "ios-xe",
      "created_at": "2026-08-15T09:30:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 25,
  "has_next": false
}
```

**Frontend Use Case:** Show how a device's attributes changed across multiple discoveries

---

### 3. Comparison Result
**Endpoint:** `GET /comparison/{run_id}`

**Response:**
```json
{
  "id": "uuid",
  "expected_snapshot_id": "uuid",
  "observed_snapshot_id": "uuid",
  "compared_at": "2026-08-15T09:30:10Z",
  "metrics": {
    "total_differences": 5,
    "total_findings": 5,
    "missing": 1,
    "unexpected": 1,
    "modified": 3,
    "conflict": 0,
    "duplicate": 0,
    "unsupported": 0,
    "unknown": 0
  },
  "findings": [
    {"id": "uuid", "rule_id": "uuid"},
    ...
  ]
}
```

**Frontend Use Case:** Show metrics summary for a comparison run

---

### 4. Findings List
**Endpoint:** `GET /findings`

**Query Parameters:**
- `page` (int, default=1): Pagination
- `page_size` (int, default=20): Items per page (max 200)

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "finding_id": "uuid",
      "rule_id": "uuid",
      "title": "NetBox device switch-01 is missing live.",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "description": "Device expected from NetBox inventory not found in real network.",
      "expected_state": {
        "value": "switch-01",
        "difference_type": "missing"
      },
      "observed_state": {
        "value": null
      },
      "evidence": [
        {
          "id": "uuid",
          "source": "comparison",
          "description": "NetBox device identity not matched in live snapshot",
          "reference": "switch-01",
          "details": {
            "expected_name": "switch-01",
            "observed_name": null,
            "match_confidence": 0.0
          },
          "captured_at": "2026-08-15T09:30:10Z"
        }
      ],
      "created_at": "2026-08-15T09:30:10Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 150,
  "has_next": true
}
```

**Frontend Use Case:** Main findings/variances view with severity indicators

---

### 5. Single Finding Detail
**Endpoint:** `GET /findings/{finding_id}`

**Response:** Same as findings list item, but single record

**Frontend Use Case:** Detailed investigation of a specific variance

---

## API Patterns

### Pagination
All list endpoints support:
- `page` (1-indexed): 1, 2, 3, ...
- `page_size`: 1-200 (typically 20-50 for UI)
- Response includes `has_next` boolean

### Timestamps
All datetime fields are ISO 8601 format with timezone: `2026-08-15T09:30:10Z`

### Error Handling
Errors return:
```json
{
  "detail": "Error message"
}
```
HTTP status codes: 404 (not found), 400 (bad request), 500 (server error)

---

## Frontend Feature Mapping

### Feature: Show Network Variance Dashboard
**Flow:**
1. `GET /history/discovery-runs` → Latest discovery run
2. `GET /findings?page_size=50` → Top variances
3. Display metrics from findings

### Feature: Investigate a Specific Variance
**Flow:**
1. User clicks on a finding
2. `GET /findings/{finding_id}` → Full details with evidence
3. Display expected state vs observed state
4. Show evidence chain

### Feature: Track Device Changes Over Time
**Flow:**
1. User selects a device (e.g., "switch-01")
2. `GET /devices/switch-01/history` → Historical observations
3. Display timeline of changes

### Feature: Review Discovery Run
**Flow:**
1. User clicks on a discovery run
2. `GET /comparison/{run_id}` → Metrics and findings
3. `GET /findings?related_to={run_id}` → Findings for this run
4. Display results

---

## API Limits & Performance

### Pagination
- Default: 20 items
- Max: 200 items per page
- Typical frontend usage: 20-50 items

### Response Times
- `/history/discovery-runs`: <100ms
- `/findings`: <200ms (paginated)
- `/findings/{id}`: <50ms
- `/devices/{id}/history`: <100ms
- `/comparison/{id}`: <50ms

### Database Queries
All endpoints use indexed queries:
- `discovery_runs` table indexed on `created_at`
- `findings` table indexed on `comparison_result_id`
- `snapshot_devices` indexed on `device_id`
- `comparison_results` indexed on IDs

---

## Next Phase API Gaps

These endpoints don't exist yet but could be added in M30:

### Gap 1: Get Latest NetBox Inventory
```
GET /inventory/netbox → List of expected devices
```
Workaround: Query latest NetBox snapshot from comparison API

### Gap 2: Get Latest Live Inventory
```
GET /inventory/live → List of discovered devices
```
Workaround: Query latest live snapshot from device history

### Gap 3: Unified Timeline
```
GET /history/timeline → Merged runs + comparisons
```
Workaround: Fetch separately and merge in frontend

### Gap 4: Device State Comparison
```
GET /devices/{device_id}/state → Expected vs observed side-by-side
```
Workaround: Construct from findings that reference the device

---

## Schema Mapping (For API consumers)

### Finding Severity Levels
- `CRITICAL`: Device missing or major mismatch
- `HIGH`: Important attribute changed (IP, serial)
- `MEDIUM`: Interface or VLAN issue
- `LOW`: Non-critical metadata
- `INFO`: Neighbor or informational

### Difference Types (in findings)
- `missing`: Expected but not found
- `unexpected`: Found but not expected
- `modified`: Attribute mismatch
- `conflict`: Ambiguous match
- `duplicate`: Identity collision
- `unsupported`: No baseline for validation

### Discovery Status
- `started`: Discovery run in progress
- `succeeded`: Completed successfully
- `failed`: Error occurred

---

## Example Frontend Implementations

### Show Latest Variances
```
GET /findings?page_size=10&page=1

Then display:
- Title (from finding)
- Severity (color-coded)
- Expected vs Observed (from finding.expected_state / observed_state)
- Evidence details (timestamp, source)
```

### Show Variance Timeline
```
GET /history/discovery-runs?page_size=20

Then for each run:
- Run status
- Timestamp
- Metadata (site, role, platform)
- Link to comparisons
```

### Device Deep Dive
```
GET /devices/switch-01/history?page_size=20

Display table:
- Date / Time
- Name
- Model
- Serial
- Platform
```

---

## Testing the API (CLI)

```bash
# List discovery runs
curl http://localhost:8000/history/discovery-runs?page_size=5

# Get findings
curl http://localhost:8000/findings?page_size=10

# Get specific finding
curl http://localhost:8000/findings/{finding-uuid}

# Get device history
curl http://localhost:8000/devices/switch-01/history

# Get comparison result
curl http://localhost:8000/comparison/{comparison-uuid}
```

---

## Notes for Frontend Team

1. **All data is immutable** — No PUT/PATCH/DELETE needed. Only GET.
2. **No authentication implemented yet** — APIs are open for M29.5.
3. **Pagination is important** — Some lists could have 1000+ items.
4. **Timestamps are all UTC** — Client can convert to local timezone.
5. **Full lineage is available** — Can trace from finding → evidence → snapshots.
6. **No polling recommended** — Set last_check_at in frontend if needed.

---

## Questions?

See the detailed technical audit in: **[M29.5-CAPABILITY-AUDIT.md](M29.5-CAPABILITY-AUDIT.md)**
