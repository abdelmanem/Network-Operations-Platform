import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'

const {
  mockLogin,
  mockGetCurrentUser,
  mockGetDashboardKpis,
  mockGetDashboardTrends,
  mockGetJobs,
} = vi.hoisted(() => ({
  mockLogin: vi.fn(),
  mockGetCurrentUser: vi.fn(),
  mockGetDashboardKpis: vi.fn(),
  mockGetDashboardTrends: vi.fn(),
  mockGetJobs: vi.fn(),
}))

vi.mock('../services/api', () => ({
  login: mockLogin,
  getCurrentUser: mockGetCurrentUser,
}))

vi.mock('../api/dashboard', () => ({
  getDashboardKpis: mockGetDashboardKpis,
  getDashboardTrends: mockGetDashboardTrends,
}))

vi.mock('../api/jobs', () => ({
  getJobs: mockGetJobs,
  cancelJob: vi.fn(),
}))

describe('frontend foundation shell', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mockGetCurrentUser.mockResolvedValue({
      username: 'demo',
      email: 'demo@example.com',
      roles: ['admin'],
    })
    mockGetDashboardKpis.mockResolvedValue({
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
      latest_run_id: null,
      latest_run_started_at: null,
      latest_run_finished_at: null,
      unsupported_metrics: [],
    })
    mockGetDashboardTrends.mockResolvedValue({
      trends: {
        discovery_success_trend: {
          metric: 'discovery_success',
          baseline_value: 80,
          current_value: 83,
          trend: 'increasing',
          direction: 'up',
          period_start: null,
          period_end: null,
        },
        device_count_trend: {
          metric: 'device_count',
          baseline_value: 10,
          current_value: 12,
          trend: 'increasing',
          direction: 'up',
          period_start: null,
          period_end: null,
        },
        findings_count_trend: {
          metric: 'findings_count',
          baseline_value: 3,
          current_value: 4,
          trend: 'increasing',
          direction: 'up',
          period_start: null,
          period_end: null,
        },
        drift_trend: {
          metric: 'drift',
          baseline_value: 0,
          current_value: 1,
          trend: 'volatile',
          direction: 'up',
          period_start: null,
          period_end: null,
        },
      },
    })
    mockGetJobs.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
      has_next: false,
    })
  })

  it('renders the login screen when unauthenticated', () => {
    window.history.pushState({}, '', '/login')
    render(<App />)
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows an authentication failure message', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid credentials'))
    window.history.pushState({}, '', '/login')
    render(<App />)

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'demo' },
    })
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'wrong' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument()
  })

  it('authenticates successfully and shows the dashboard shell', async () => {
    mockLogin.mockResolvedValueOnce({ access_token: 'token', refresh_token: 'refresh', token_type: 'bearer' })
    window.history.pushState({}, '', '/login')
    render(<App />)

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'demo' },
    })
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'secret' },
    })
    fireEvent.click(screen.getByRole('button', { name: /continue/i }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument()
    })
  })

  it('redirects protected routes to login when unauthenticated', async () => {
    window.history.pushState({}, '', '/dashboard')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  })

  it('renders shell navigation and the jobs empty state', async () => {
    localStorage.setItem('auth-token', 'token')
    window.history.pushState({}, '', '/jobs')
    render(<App />)

    expect(await screen.findByRole('heading', { name: /jobs/i })).toBeInTheDocument()
    expect(screen.getByRole('navigation')).toBeInTheDocument()
    expect(screen.getByText(/no jobs have been created yet/i)).toBeInTheDocument()
  })

  it('shows a dashboard error state when the backend contract is unavailable', async () => {
    mockGetDashboardKpis.mockRejectedValueOnce(new Error('Service unavailable'))
    mockGetDashboardTrends.mockRejectedValueOnce(new Error('Service unavailable'))
    localStorage.setItem('auth-token', 'token')
    window.history.pushState({}, '', '/dashboard')
    render(<App />)

    expect(await screen.findByText(/service unavailable/i)).toBeInTheDocument()
  })

  it('supports logout from the authenticated shell', async () => {
    localStorage.setItem('auth-token', 'token')
    window.history.pushState({}, '', '/dashboard')
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/operations dashboard/i)).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }))
    expect(await screen.findByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  })
})
