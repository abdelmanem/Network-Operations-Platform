# Milestone 25 Dashboard Backend Contract

## Purpose

This document captures the Milestone 25 dashboard backend contract before implementation.
It defines the dashboard KPIs, authoritative sources, aggregation semantics, trend semantics, tenant/scope behavior, and explicit view model contracts.

The dashboard backend is a projection/consumption layer only. It must reuse existing persisted history, reporting, analytics, discovery, compliance, and evaluation capabilities wherever they are authoritative.

## Scope

Milestone 25 will implement:

1. KPI services
2. Aggregated statistics
3. Trend services
4. Dashboard view models

It will not implement UI, charts, AI/ML, predictive analytics, notification changes, scheduler changes, audit/activity logging, or unrelated database redesign.

## Dashboard KPI Catalog

### 1. Discovery Run KPIs

- `discovery_success_pct`
  - Source: latest persisted `DiscoveryRunRecord` from `HistoryRepository.list_discovery_runs()`
  - Existing service/repository: `backend.app.history.discovery.DiscoveryHistory` / `backend.app.persistence.repositories.HistoryRepository`
  - Type: point-in-time
  - Semantics: latest discovery run success ratio using `successful_targets / total_targets`
  - Tenant/scope: optional metadata filters can be applied from `DiscoveryRunRecord.metadata_json` if present
  - View model: `DashboardDiscoveryRunSummary`

- `failed_targets`, `skipped_targets`, `successful_targets`, `total_targets`
  - Source: latest persisted `DiscoveryRunRecord`
  - Type: point-in-time
  - Semantics: latest discovery run counts
  - View model: `DashboardDiscoveryRunSummary`

### 2. Inventory Snapshot KPIs

- `total_devices`
  - Source: latest live `SnapshotRecord` from `SnapshotRepository.list_by_source(SnapshotSource.LIVE)`
  - Existing service/repository: `backend.app.history.snapshots.SnapshotHistory` / `backend.app.persistence.repositories.SnapshotRepository`
  - Type: point-in-time
  - Semantics: device count in latest live inventory snapshot
  - View model: `DashboardInventorySummary`

- `reachable_devices`
  - Source: latest live snapshot device count, or latest discovery run `successful_targets` when live snapshot is unavailable
  - Type: point-in-time
  - Semantics: count of successfully discovered devices in latest available state
  - View model: `DashboardInventorySummary`

- `unreachable_devices`
  - Source: derived from latest discovery run (`total_targets - successful_targets`)
  - Existing semantics: discovery run indicates planned targets vs successful connections
  - Type: point-in-time
  - View model: `DashboardInventorySummary`

### 3. Comparison/Drift KPIs

- `missing_devices`, `extra_devices`, `modified_devices`
  - Source: latest persisted `ComparisonResultRecord.metrics` from `FindingRepository.get_comparison_result()` or directly from the latest `ComparisonResultRecord`
  - Existing service/repository: `backend.app.persistence.repositories.FindingRepository`
  - Type: point-in-time
  - Semantics: drift counts from the latest comparison result
  - View model: `DashboardDriftSummary`

- `findings_total`
  - Source: latest persisted `ComparisonResultRecord.findings`
  - Type: point-in-time
  - Semantics: number of findings in latest comparison result
  - View model: `DashboardDriftSummary`

- `finding_severity_counts`
  - Source: latest persisted `FindingRecord.severity` values from `FindingRepository` or latest comparison findings
  - Type: point-in-time
  - Semantics: severity distribution for latest comparison findings
  - View model: `DashboardFindingCounts`

### 4. Data Quality KPIs

- `netbox_accuracy_pct`
  - Source: latest comparison metrics plus latest NetBox snapshot device count
  - Existing semantics: derived in `reporting.statistics.StatisticsCalculator` from `comparison_result.metrics` and `netbox_inventory`
  - Type: point-in-time
  - Semantics: percent of NetBox inventory devices matched by live discovery, using persisted comparison and snapshot data
  - View model: `DashboardQualitySummary`

### 5. Trend KPIs

- `discovery_success_trend`
  - Source: historical discovery run records mapped to time-ordered series
  - Existing service/repository: `HistoryRepository.list_discovery_runs()` and analytics trend classification helpers
  - Type: trend
  - Semantics: classification of discovery success over a selected period
  - View model: `DashboardTrendSummary`

- `device_count_trend`
  - Source: historical live snapshot device counts or discovery totals from persisted runs
  - Type: trend
  - Semantics: trend for discovered device counts across runs
  - View model: `DashboardTrendSummary`

- `findings_count_trend`
  - Source: historical comparison result finding counts
  - Type: trend
  - Semantics: trend for number of findings across comparison results
  - View model: `DashboardTrendSummary`

- `drift_trend`
  - Source: historical comparison metrics counts (`missing`, `unexpected`, `modified`)
  - Type: trend
  - Semantics: classification of inventory drift across persisted comparisons
  - View model: `DashboardTrendSummary`

### 6. Aggregate Statistics

- `run_aggregates`
  - Source: historical discovery run records and/or comparison results
  - Existing service/repository: `HistoryRepository`, `SnapshotRepository`, and optionally analytics aggregation helpers
  - Type: aggregated time buckets
  - Semantics: bucket historical runs by period (`daily`, `weekly`, `monthly`) and summarize counts and ratios
  - View model: `DashboardAggregateBucket`

- `finding_aggregates`
  - Source: historical comparison findings and differences
  - Type: aggregated time buckets
  - Semantics: aggregated findings counts and severity distribution by period
  - View model: `DashboardAggregateBucket`

## Authoritative Source Matrix

| KPI | Authoritative Source | Existing Repository/Service | Data Type | Semantics |
|---|---|---|---|---|
| discovery_success_pct | `DiscoveryRunRecord` | `HistoryRepository` | point-in-time | Latest run discovery success ratio |
| total_devices | `SnapshotRecord` (LIVE) | `SnapshotRepository` | point-in-time | Latest live inventory device count |
| reachable_devices | `SnapshotRecord` (LIVE) / `DiscoveryRunRecord` | `SnapshotRepository` / `HistoryRepository` | point-in-time | Latest discovered reachable devices |
| unreachable_devices | `DiscoveryRunRecord` | `HistoryRepository` | point-in-time | Derived from planned vs successful targets |
| missing_devices | `ComparisonResultRecord.metrics` | `FindingRepository` | point-in-time | Latest comparison missing count |
| extra_devices | `ComparisonResultRecord.metrics` | `FindingRepository` | point-in-time | Latest comparison unexpected count |
| modified_devices | `ComparisonResultRecord.metrics` | `FindingRepository` | point-in-time | Latest comparison modified count |
| findings_total | `FindingRecord` / `ComparisonResultRecord.findings` | `FindingRepository` | point-in-time | Latest comparison findings count |
| finding_severity_counts | `FindingRecord.severity` | `FindingRepository` | point-in-time | Latest comparison severity distribution |
| netbox_accuracy_pct | `ComparisonResultRecord.metrics` + NetBox snapshot size | `FindingRepository` + `SnapshotRepository` | point-in-time | Latest match accuracy against NetBox inventory |
| discovery_success_trend | historical discovery run series | `HistoryRepository` | trend | Comparison of latest vs baseline discovery success |
| device_count_trend | historical snapshot/run series | `SnapshotRepository` / `HistoryRepository` | trend | Change in discovered device count |
| findings_count_trend | historical comparison findings | `FindingRepository` | trend | Change in findings volume |
| drift_trend | historical comparison metrics | `FindingRepository` | trend | Change in drift counts |
| run_aggregates | historical discovery run series | `HistoryRepository` | aggregate | Bucketed run stats by period |

## Gaps and Constraints

### Evaluation-based KPIs

- `compliance_score` and `risk_score` are not currently persisted to the database schema.
- The existing persisted history model contains discovery runs, snapshots, comparison results, findings, and evidence only.
- `ReportService` can build report context from a live orchestration result, but that is not authoritative for persisted dashboard history.
- Therefore, Milestone 25 must not invent compliance/risk KPIs from unpersisted state.
- If such KPIs are required later, they must be supported by a separate persistence change or a well-defined in-memory dashboard contract that is explicitly outside the current history data model.

### Tenant/Security Scope

- There is no explicit tenant model in current persisted history APIs.
- `DiscoveryRunRecord.metadata_json` can carry tenant-like metadata such as `site` and `device_role`.
- `ReportContext` already exposes `site` and `device_role` as optional fields.
- Dashboard filters may therefore be implemented as optional metadata filtering on persisted discovery runs and snapshots.
- Existing security boundaries are enforced via `get_current_user()` and authorization services in `backend.app.auth.api.dependencies`, but current history APIs do not enforce tenant restrictions.
- For Milestone 25, dashboard routes should preserve this boundary by:
  - validating optional filters (`site`, `device_role`, `platform`)
  - not bypassing authentication/authorization mechanisms already present in the app
  - restricting aggregates and trends to filtered persisted history when filters are supplied

### Existing Service Reuse

- Reuse `HistoryRepository`, `SnapshotRepository`, and `FindingRepository` for data access.
- Reuse `reporting.statistics.StatisticsCalculator` semantics for point-in-time summary calculations when possible.
- Reuse `analytics.trends.classify_trend` for descriptive trend classification.
- Reuse `analytics.aggregation.aggregate_runs` only for compatible bucket semantics and when the persisted history can provide required metrics.

## Proposed Dashboard Service Boundaries

### Service layer

- `DashboardService`
  - `current_kpis(...) -> DashboardKpiSummary`
  - `aggregated_statistics(...) -> DashboardAggregateResponse`
  - `trends(...) -> DashboardTrendsResponse`
  - `kpi_by_site(...) -> DashboardKpiSummary` (optional)

- `DashboardRepositoryAdapter`
  - `list_discovery_runs(...)`
  - `list_live_snapshots(...)`
  - `get_latest_comparison_result(...)`
  - `list_findings_for_comparison(...)`

### View model contracts

- `DashboardKpiSummary`
  - total_devices: int
  - reachable_devices: int
  - unreachable_devices: int
  - discovery_success_pct: float
  - netbox_accuracy_pct: float | None
  - missing_devices: int
  - extra_devices: int
  - modified_devices: int
  - findings_total: int
  - critical_findings: int
  - major_findings: int
  - minor_findings: int
  - latest_run_id: UUID | None
  - latest_run_started_at: datetime | None
  - latest_run_finished_at: datetime | None

- `DashboardAggregateBucket`
  - period_label: str
  - start: datetime
  - end: datetime
  - discovery_success_pct: float | None
  - total_devices: int | None
  - missing_devices: int
  - extra_devices: int
  - modified_devices: int
  - findings_total: int

- `DashboardTrendEntry`
  - metric: str
  - baseline_value: float | int | None
  - current_value: float | int | None
  - trend: str
  - direction: str
  - period_start: datetime | None
  - period_end: datetime | None

- `DashboardTrendsResponse`
  - discovery_success_trend: DashboardTrendEntry
  - device_count_trend: DashboardTrendEntry
  - findings_count_trend: DashboardTrendEntry
  - drift_trend: DashboardTrendEntry

- `DashboardResponseEnvelope`
  - summary: DashboardKpiSummary
  - aggregates: list[DashboardAggregateBucket]
  - trends: DashboardTrendsResponse

## API Contracts

- `GET /api/v1/dashboard/kpis`
  - query params: `site`, `device_role`, `platform`, `start_date`, `end_date`
  - returns: `DashboardKpiSummaryResponse`
  - semantics: latest persisted run/snapshot comparison state filtered by optional scopes

- `GET /api/v1/dashboard/aggregates`
  - query params: `granularity` (`daily`, `weekly`, `monthly`), `site`, `device_role`, `platform`, `start_date`, `end_date`
  - returns: `DashboardAggregateListResponse`

- `GET /api/v1/dashboard/trends`
  - query params: `period` or `start_date`/`end_date`, `site`, `device_role`, `platform`
  - returns: `DashboardTrendsResponse`

## Empty / No Data Behavior

- No-data responses should remain deterministic and typed.
- KPI values should default to zero or `null` where appropriate.
- Aggregate buckets should return an empty list when no history matches.
- Trend summaries should classify empty or single-point series as `stable` with zero/`null` numeric values.
- No route should return raw ORM models or untyped payloads.

## Deterministic Ordering

- Historical runs and aggregates must be ordered oldest-to-newest for trends.
- Aggregated time buckets must be ordered by `start` ascending.
- `HistoryRepository.list_discovery_runs()` currently returns newest-first; dashboard code must reverse for trend series.

## Limitations and Gaps

- `compliance_score` and `risk_score` are not supported by authoritative persisted history today.
- Tenant security enforcement is currently limited by the absence of a first-class persisted tenant model; dashboard filters can use metadata, but explicit authorization enforcement is outside Milestone 25.
- `netbox_accuracy_pct` can only be calculated when the latest comparison result and NetBox snapshot exist.

## Implementation Guidance

- Keep route handlers thin and delegate all computation to `DashboardService`.
- Build typed view models in `backend.app.dashboard.models` and `backend.app.schemas.dashboard`.
- Use existing repository classes for data access.
- Avoid introducing new persistence schema or audit logging.
- Validate all request parameters in API routes.
- Add milestone-specific tests that cover KPI service results, aggregation semantics, trend semantics, empty data, deterministic ordering, and view-model serialization.
- Preserve existing analytics/reporting behavior by not modifying current reporting classes unless reuse is explicitly beneficial.
