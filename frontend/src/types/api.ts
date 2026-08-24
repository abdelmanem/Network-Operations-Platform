export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserResponse {
  username: string
  email: string
  roles: string[]
  permissions?: string[]
}

export interface DashboardKpiSummaryResponse {
  total_devices: number | null
  reachable_devices: number | null
  unreachable_devices: number | null
  discovery_success_pct: number | null
  netbox_accuracy_pct: number | null
  missing_devices: number | null
  extra_devices: number | null
  modified_devices: number | null
  findings_total: number | null
  critical_findings: number | null
  major_findings: number | null
  minor_findings: number | null
  latest_run_id: string | null
  latest_run_started_at: string | null
  latest_run_finished_at: string | null
  unsupported_metrics: string[]
}

export interface DashboardAggregateBucketResponse {
  period_label: string
  start: string
  end: string
  discovery_success_pct: number | null
  total_devices: number | null
  missing_devices: number | null
  extra_devices: number | null
  modified_devices: number | null
  findings_total: number | null
}

export interface DashboardTrendEntryResponse {
  metric: string
  baseline_value: number | null
  current_value: number | null
  trend: 'stable' | 'increasing' | 'decreasing' | 'volatile'
  direction: 'up' | 'down' | 'flat'
  period_start: string | null
  period_end: string | null
}

export interface DashboardTrendsResponseEnvelope {
  trends: {
    discovery_success_trend: DashboardTrendEntryResponse
    device_count_trend: DashboardTrendEntryResponse
    findings_count_trend: DashboardTrendEntryResponse
    drift_trend: DashboardTrendEntryResponse
  }
}

export interface DiscoveryRunSummaryResponse {
  id: string
  target_identifier: string
  target_address: string | null
  status: string
  metadata: Record<string, unknown>
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface DiscoveryRunListResponse {
  items: DiscoveryRunSummaryResponse[]
  page: number
  page_size: number
  total: number
  has_next: boolean
}

export interface DiscoveryJobRequest {
  collector_contexts: Array<{
    target: {
      identifier: string
      address: string
      metadata?: Record<string, unknown>
    }
  }>
  policies: Array<Record<string, unknown>>
  metadata: Record<string, unknown>
  priority: number
  timeout_seconds: number | null
}

export interface DiscoveryJobSubmissionResponse {
  job_id: string
  status: string
  message: string
}

export interface DiscoveryTargetRequest {
  identifier: string
  address?: string | null
  scope_type: 'single_device' | 'ip_range' | 'cidr_network'
  scope_end?: string | null
  scope_cidr?: string | null
  tenant_id: string
  hostname?: string | null
  vendor?: string | null
  platform_hint?: string | null
  preferred_transport?: string | null
  enabled: boolean
  credential_reference?: string | null
  credential_profile_id: string
  credential_references?: Record<string, string>
  allowed_fallback_transports?: string[]
  metadata: Record<string, unknown>
}

export interface DiscoveryTargetResponse {
  target_id: string
  tenant_id: string
  identifier: string
  address: string
  vendor: string | null
  scope_type: 'single_device' | 'ip_range' | 'cidr_network'
  scope_end: string | null
  scope_cidr: string | null
  credential_profile_id: string | null
  platform_hint: string | null
  preferred_transport: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CredentialProfileRequest {
  name: string
  description?: string | null
  vendor?: string | null
  platform?: string | null
  credential_type?: string | null
  username?: string | null
  transport_types: string[]
  provider_reference: string
}

export interface CredentialProfileResponse {
  profile_id: string
  tenant_id: string
  name: string
  description: string | null
  transport_types: string[]
  provider_reference: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CredentialProfileTestRequest {
  transport: string
  target: string
}

export interface CredentialProfileTestResponse {
  status: string
  transport: string
  target: string
  credential_type?: string | null
  message: string
  provider_reference?: string | null
}

export interface DiscoveryApiJobRequest {
  target_id: string
  requested_capabilities: Record<string, unknown>
  metadata: Record<string, unknown>
  timeout_seconds?: number | null
  correlation_id?: string | null
}

export interface DiscoveryApiJobResponse {
  job_id: string
  tenant_id: string
  target_id: string
  discovery_run_id: string | null
  status:
    'queued' | 'running' | 'succeeded' | 'failed' | 'timed_out' | 'cancelled'
  selected_transport: string | null
  selected_platform: string | null
  attempts: number
  error_code: string | null
  error_message: string | null
  created_at: string
  queued_at: string | null
  started_at: string | null
  finished_at: string | null
  timeout_seconds: number | null
  correlation_id: string | null
  cancellation_requested_at: string | null
  cancellation_requested_by: string | null
  cancellation_reason: string | null
}

export interface DiscoveryJobListResponse {
  items: DiscoveryApiJobResponse[]
  page: number
  page_size: number
  total: number
  has_next: boolean
}

export interface DiscoveryEvidenceResponse {
  evidence_id: string
  tenant_id: string
  target_id: string
  discovery_job_id: string
  discovery_run_id: string
  collector_name: string
  platform: string
  transport: string
  evidence_type: string
  command_or_probe: string
  payload: Record<string, unknown>
  captured_at: string
  sequence: number
  parser_version: string | null
  normalization_version: string | null
  content_hash: string
}

export interface DiscoveryDeviceResultResponse {
  result_id: string
  address: string
  hostname: string | null
  vendor: string | null
  model: string | null
  platform: string | null
  state: string
  selected_transport: string | null
  failure_code: string | null
  failure_message: string | null
  started_at: string | null
  completed_at: string | null
  correlation_id: string | null
}

export interface JobStatusResponse {
  job_id: string
  status: string
  message: string | null
  created_at: string
  updated_at: string
  attempts: number
  progress: number | null
}

export interface JobListResponse {
  items: JobStatusResponse[]
  page: number
  page_size: number
  total: number
  has_next: boolean
}

// ============================================================================
// M30.1 Network Operations APIs
// ============================================================================

// Inventory types
export interface DeviceSnapshotItem {
  device_id: string
  name: string
  manufacturer: string | null
  model: string | null
  serial_number: string | null
  product_id: string | null
  management_ip: string | null
  platform: string | null
}

export interface InventoryListResponse {
  items: DeviceSnapshotItem[]
  page: number
  page_size: number
  total: number
  has_next: boolean
  source: string
  snapshot_id: string | null
  snapshot_captured_at: string | null
  device_count: number
  manufacturers: string[]
  platforms: string[]
}

// Snapshot types
export interface SnapshotResponse {
  id: string
  source: string
  device_count: number
  interface_count: number
  vlan_count: number
  neighbor_count: number
  captured_at: string
}

export interface InterfaceResponse {
  name: string
  admin_status: string | null
  oper_status: string | null
  description: string | null
  mac_address: string | null
  speed_mbps: number | null
  poe_status: string | null
}

export interface InterfaceListResponse {
  snapshot_id: string
  device_id: string
  interface_count: number
  items: InterfaceResponse[]
}

export interface VlanResponse {
  vlan_id: number
  name: string
  status: string | null
}

export interface VlanListResponse {
  snapshot_id: string
  device_id: string
  vlan_count: number
  items: VlanResponse[]
}

export interface NeighborResponse {
  neighbor_id: string
  remote_device_id: string
  remote_interface: string | null
  local_interface: string | null
  protocol: string | null
}

export interface NeighborListResponse {
  snapshot_id: string
  device_id: string
  neighbor_count: number
  items: NeighborResponse[]
}

export interface SnapshotDeviceListResponse {
  snapshot_id: string
  source: string
  device_count: number
  items: Record<string, unknown>[]
}

// Comparison types
export interface ComparisonState {
  device_id: string
  name: string | null
  manufacturer: string | null
  model: string | null
  serial_number: string | null
  product_id: string | null
  management_ip: string | null
  platform: string | null
}

export interface VarianceSummary {
  field_name: string
  expected_value: unknown | null
  observed_value: unknown | null
  difference_type: string
}

export interface DeviceComparisonResponse {
  device_id: string
  comparison_result_id: string | null
  compared_at: string | null
  expected_state: ComparisonState | null
  observed_state: ComparisonState | null
  variances: VarianceSummary[]
}

// NetBox Integration types
export interface InventoryCounts {
  devices: number
  interfaces: number
  ip_addresses: number
  vlans: number
}

export interface NetBoxIntegrationStatusResponse {
  configured: boolean
  connected: boolean
  tls_verified: boolean
  authenticated: boolean
  version: string | null
  hostname: string | null
  last_successful_sync: string | null
  current_sync_status: 'idle' | 'queued' | 'running' | 'succeeded' | 'failed'
  sync_started_at: string | null
  sync_completed_at: string | null
  sync_error: string | null
  inventory_counts: InventoryCounts
}

export interface NetBoxTestConnectionResponse {
  connected: boolean
  tls_verified: boolean
  authenticated: boolean
  version: string | null
  hostname: string | null
  message: string
}

export interface NetBoxSyncResponse {
  job_id: string
  status: string
}

export interface NetBoxErrorContract {
  code: string
  message: string
  details: unknown | null
}
