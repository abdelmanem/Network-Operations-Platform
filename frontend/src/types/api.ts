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
