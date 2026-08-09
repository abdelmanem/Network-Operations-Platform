import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from '../pages/DashboardPage'
import type {
  DashboardKpiSummaryResponse,
  DashboardTrendsResponseEnvelope,
} from '../types/api'

const { mockGetDashboardKpis, mockGetDashboardTrends } = vi.hoisted(() => ({
  mockGetDashboardKpis: vi.fn(),
  mockGetDashboardTrends: vi.fn(),
}))

vi.mock('../api/dashboard', () => ({
  getDashboardKpis: mockGetDashboardKpis,
  getDashboardTrends: mockGetDashboardTrends,
}))

function makeKpis(overrides: Partial<DashboardKpiSummaryResponse> = {}): DashboardKpiSummaryResponse {
  return {
    total_devices: 12,
    reachable_devices: 10,
    unreachable_devices: 2,
    discovery_success_pct: 83,
    netbox_accuracy_pct: 91,
    missing_devices: 0,
    extra_devices: 1,
    modified_devices: 1,
    findings_total: 4,
    critical_findings: 0,
    major_findings: 1,
    minor_findings: 3,
    latest_run_id: 'run-001',
    latest_run_started_at: '2026-08-09T10:00:00Z',
    latest_run_finished_at: '2026-08-09T10:05:00Z',
    unsupported_metrics: [],
    ...overrides,
  }
}

function makeTrends(overrides: Partial<DashboardTrendsResponseEnvelope['trends']> = {}): DashboardTrendsResponseEnvelope {
  return {
    trends: {
      discovery_success_trend: {
        metric: 'discovery_success',
        baseline_value: 80,
        current_value: 83,
        trend: 'increasing',
        direction: 'up',
        period_start: '2026-08-01',
        period_end: '2026-08-09',
      },
      device_count_trend: {
        metric: 'device_count',
        baseline_value: 10,
        current_value: 12,
        trend: 'increasing',
        direction: 'up',
        period_start: '2026-08-01',
        period_end: '2026-08-09',
      },
      findings_count_trend: {
        metric: 'findings_count',
        baseline_value: 3,
        current_value: 4,
        trend: 'increasing',
        direction: 'up',
        period_start: '2026-08-01',
        period_end: '2026-08-09',
      },
      drift_trend: {
        metric: 'drift',
        baseline_value: 0,
        current_value: 1,
        trend: 'volatile',
        direction: 'up',
        period_start: '2026-08-01',
        period_end: '2026-08-09',
      },
      ...overrides,
    },
  }
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a loading state while dashboard data is requested', () => {
    mockGetDashboardKpis.mockReturnValueOnce(new Promise(() => {}))
    mockGetDashboardTrends.mockReturnValueOnce(new Promise(() => {}))

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    expect(screen.getByText(/loading dashboard data/i)).toBeInTheDocument()
  })

  it('renders KPI cards and trend data from the backend contract', async () => {
    mockGetDashboardKpis.mockResolvedValueOnce(makeKpis())
    mockGetDashboardTrends.mockResolvedValueOnce(makeTrends())

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/total devices/i)).toBeInTheDocument()
    })
    expect(screen.getAllByText(/discovery success/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/device count/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/83/i).length).toBeGreaterThan(0)
  })

  it('shows an empty state when the backend returns no operational data', async () => {
    mockGetDashboardKpis.mockResolvedValueOnce(
      makeKpis({
        total_devices: null,
        reachable_devices: null,
        unreachable_devices: null,
        discovery_success_pct: null,
        netbox_accuracy_pct: null,
        missing_devices: null,
        extra_devices: null,
        modified_devices: null,
        findings_total: null,
        critical_findings: null,
        major_findings: null,
        minor_findings: null,
      }),
    )
    mockGetDashboardTrends.mockResolvedValueOnce(
      makeTrends({
        discovery_success_trend: {
          metric: 'discovery_success',
          baseline_value: null,
          current_value: null,
          trend: 'stable',
          direction: 'flat',
          period_start: null,
          period_end: null,
        },
        device_count_trend: {
          metric: 'device_count',
          baseline_value: null,
          current_value: null,
          trend: 'stable',
          direction: 'flat',
          period_start: null,
          period_end: null,
        },
        findings_count_trend: {
          metric: 'findings_count',
          baseline_value: null,
          current_value: null,
          trend: 'stable',
          direction: 'flat',
          period_start: null,
          period_end: null,
        },
        drift_trend: {
          metric: 'drift',
          baseline_value: null,
          current_value: null,
          trend: 'stable',
          direction: 'flat',
          period_start: null,
          period_end: null,
        },
      }),
    )

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/no operational data is currently available/i)).toBeInTheDocument()
  })

  it('shows an error state and allows retrying dashboard requests', async () => {
    mockGetDashboardKpis.mockRejectedValueOnce(new Error('Service unavailable'))
    mockGetDashboardTrends.mockRejectedValueOnce(new Error('Service unavailable'))

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/unable to load dashboard data/i)).toBeInTheDocument()

    mockGetDashboardKpis.mockResolvedValueOnce(makeKpis())
    mockGetDashboardTrends.mockResolvedValueOnce(makeTrends())

    fireEvent.click(await screen.findByRole('button', { name: /retry/i }))

    await waitFor(() => {
      expect(screen.getByText(/total devices/i)).toBeInTheDocument()
    })
  })
})
