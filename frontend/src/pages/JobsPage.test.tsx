import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { discoveryJobsErrorTitle } from '../api/discovery'
import type { DiscoveryApiJobResponse, DiscoveryTargetResponse } from '../types/api'

const { cancelJob, resolveJob, listJobs, listTargets } = vi.hoisted(() => ({
  cancelJob: vi.fn(),
  resolveJob: vi.fn(),
  listJobs: vi.fn(),
  listTargets: vi.fn(),
}))

vi.mock('../api/discovery', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/discovery')>()),
  cancelDiscoveryApiJob: cancelJob,
  resolveDiscoveryApiJobCancellation: resolveJob,
  listDiscoveryApiJobs: listJobs,
  listDiscoveryTargets: listTargets,
}))

import { JobsPage } from './JobsPage'

function job(
  status: 'queued' | 'running' | 'succeeded' | 'failed',
  id: string = status,
): DiscoveryApiJobResponse {
  return {
    job_id: `job-${id}`,
    tenant_id: 'default',
    target_id: `target-${id}`,
    target_identifier: `target-${id}`,
    target_address: `192.168.1.${id.length}`,
    discovery_run_id: null,
    status,
    selected_transport: 'netmiko',
    selected_platform: 'cisco-iosxe',
    attempts: 1,
    error_code: status === 'failed' ? 'CONNECTION_FAILED' : null,
    error_message: status === 'failed' ? 'Connection timed out.' : null,
    created_at: '2026-08-09T10:00:00Z',
    queued_at: '2026-08-09T10:00:00Z',
    started_at: status === 'queued' ? null : '2026-08-09T10:01:00Z',
    finished_at: ['succeeded', 'failed'].includes(status)
      ? '2026-08-09T10:02:00Z'
      : null,
    timeout_seconds: null,
    correlation_id: null,
    cancellation_requested_at: null,
    cancellation_requested_by: null,
    cancellation_reason: null,
  }
}

function response(items = [job('succeeded')], page = 1, hasNext = false, totalPages = 1) {
  return {
    items,
    page,
    page_size: 25,
    total: items.length + (hasNext ? 25 : 0),
    total_pages: totalPages,
    has_next: hasNext,
  }
}

const mockTargets: DiscoveryTargetResponse[] = [
  {
    target_id: 'target-cisco-1',
    tenant_id: 'default',
    identifier: 'cisco-core',
    address: '192.168.20.0/24',
    scope_type: 'cidr_network',
    scope_end: null,
    scope_cidr: '192.168.20.0/24',
    vendor: 'cisco',
    platform_hint: 'cisco-ios',
    preferred_transport: 'netmiko',
    credential_profile_id: 'prof-1',
    enabled: true,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
  },
]

function renderPage() {
  return render(
    <MemoryRouter>
      <JobsPage />
    </MemoryRouter>,
  )
}

describe('JobsPage', () => {
  beforeEach(() => {
    listJobs.mockReset()
    cancelJob.mockReset()
    resolveJob.mockReset()
    listTargets.mockReset()
    listTargets.mockResolvedValue(mockTargets)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => vi.useRealTimers())

  it('renders discovery jobs with toolbar and displays target information', async () => {
    listJobs.mockResolvedValue(response([job('succeeded')]))
    renderPage()

    expect(await screen.findByTitle('job-succeeded')).toBeInTheDocument()
    expect(listJobs).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        page_size: 25,
      }),
    )
    expect(screen.getByText('succeeded')).toBeInTheDocument()
    expect(screen.getByText('target-succeeded')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/search jobs/i)).toBeInTheDocument()
  })

  it('renders queued, running, succeeded, and failed states with failure details and duration', async () => {
    listJobs.mockResolvedValue(
      response([
        job('queued'),
        job('running'),
        job('succeeded'),
        job('failed'),
      ]),
    )
    renderPage()

    for (const state of ['queued', 'running', 'succeeded', 'failed']) {
      expect(await screen.findByText(state)).toBeInTheDocument()
    }
    expect(screen.getByText('Connection timed out.')).toBeInTheDocument()
  })

  it('debounces free-text search and triggers API with query parameter', async () => {
    vi.useFakeTimers()
    listJobs.mockResolvedValue(response([job('succeeded', 'cisco')]))
    renderPage()

    await act(async () => {
      await Promise.resolve()
    })

    const searchInput = screen.getByPlaceholderText(/search jobs/i)
    fireEvent.change(searchInput, { target: { value: 'cisco' } })

    // Before debounce timer
    expect(listJobs).toHaveBeenCalledTimes(1)

    // Advance past debounce (300ms)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350)
    })

    expect(listJobs).toHaveBeenCalledWith(
      expect.objectContaining({
        q: 'cisco',
        page: 1,
      }),
    )
  })

  it('applies status filter and passes parameter to API', async () => {
    listJobs.mockResolvedValue(response([job('running')]))
    renderPage()

    await screen.findByText('running')

    const statusSelect = screen.getByLabelText(/^status$/i)
    fireEvent.change(statusSelect, { target: { value: 'running' } })

    await waitFor(() => {
      expect(listJobs).toHaveBeenCalledWith(
        expect.objectContaining({
          status: 'running',
          page: 1,
        }),
      )
    })
  })

  it('applies target filter and passes target_id to API', async () => {
    listJobs.mockResolvedValue(response([job('succeeded')]))
    renderPage()

    await screen.findByText('succeeded')

    await waitFor(() => {
      expect(screen.getByText(/cisco-core/i)).toBeInTheDocument()
    })

    const targetSelect = screen.getByLabelText(/^target$/i)
    fireEvent.change(targetSelect, { target: { value: 'target-cisco-1' } })

    await waitFor(() => {
      expect(listJobs).toHaveBeenCalledWith(
        expect.objectContaining({
          target_id: 'target-cisco-1',
          page: 1,
        }),
      )
    })
  })

  it('applies date filter and sort controls', async () => {
    listJobs.mockResolvedValue(response([job('succeeded')]))
    renderPage()

    await screen.findByText('succeeded')

    // Change date filter
    const dateSelect = screen.getByLabelText(/^date$/i)
    fireEvent.change(dateSelect, { target: { value: '24h' } })

    await waitFor(() => {
      expect(listJobs).toHaveBeenCalledWith(
        expect.objectContaining({
          date_from: expect.any(String),
        }),
      )
    })

    // Change sort option
    const sortSelect = screen.getByLabelText(/^sort$/i)
    fireEvent.change(sortSelect, { target: { value: 'longest_running' } })

    await waitFor(() => {
      expect(listJobs).toHaveBeenCalledWith(
        expect.objectContaining({
          sort: 'duration',
          order: 'desc',
        }),
      )
    })
  })

  it('renders an empty state when filters produce no matching jobs and allows clearing filters', async () => {
    listJobs
      .mockResolvedValueOnce(response([job('succeeded')]))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response([job('succeeded')]))
    renderPage()

    await screen.findByText('succeeded')

    // Trigger filter with no matches
    const statusSelect = screen.getByLabelText(/^status$/i)
    fireEvent.change(statusSelect, { target: { value: 'cancelled' } })

    expect(
      await screen.findByText(/no discovery jobs match the current filters/i),
    ).toBeInTheDocument()

    // Click clear filters in empty state
    const clearButtons = screen.getAllByRole('button', { name: /clear filters/i })
    fireEvent.click(clearButtons[0])

    await waitFor(() => {
      expect(listJobs).toHaveBeenCalledWith(
        expect.objectContaining({
          status: undefined,
          q: undefined,
          page: 1,
        }),
      )
    })
  })

  it('renders a true empty state when no jobs exist overall', async () => {
    listJobs.mockResolvedValue(response([]))
    renderPage()
    expect(
      await screen.findByText(/no discovery jobs have been created yet/i),
    ).toBeInTheDocument()
  })

  it('supports pagination and manual refresh preserving current filters', async () => {
    listJobs
      .mockResolvedValueOnce(response([job('succeeded', 'first')], 1, true, 2))
      .mockResolvedValueOnce(response([job('failed', 'second')], 2, false, 2))
      .mockResolvedValueOnce(response([job('failed', 'second')], 2, false, 2))
    renderPage()

    expect(await screen.findByTitle('job-first')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByTitle('job-second')).toBeInTheDocument()
    expect(listJobs).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 2,
        page_size: 25,
      }),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(listJobs).toHaveBeenCalledTimes(3))
  })

  it('displays operational warning badge for long-running suspicious active jobs', async () => {
    const staleRunningJob: DiscoveryApiJobResponse = {
      ...job('running', 'stale'),
      started_at: new Date(Date.now() - 64 * 3600 * 1000).toISOString(),
      has_active_lease: false,
      execution_owner: null,
      last_heartbeat_at: null,
    }
    listJobs.mockResolvedValue(response([staleRunningJob]))
    renderPage()

    expect(await screen.findByText(/running for 64h/i)).toBeInTheDocument()
  })

  it('links to discovery detail UI for evidence and results', async () => {
    listJobs.mockResolvedValue(response([job('succeeded', 'detail')]))
    renderPage()
    const link = await screen.findByRole('link', { name: /view details/i })
    expect(link).toHaveAttribute('href', '/discovery?job_id=job-detail')
  })

  it('shows Cancel and Resolve cancellation for active jobs and cancels appropriately', async () => {
    listJobs.mockResolvedValue(
      response([
        job('running', 'r1'),
        {
          ...job('running', 'r2'),
          cancellation_requested_at: '2026-08-09T10:01:30Z',
          has_active_lease: false,
        },
      ]),
    )
    cancelJob.mockResolvedValue({ ...job('running', 'r1'), status: 'cancelled' })
    resolveJob.mockResolvedValue({ ...job('running', 'r2'), status: 'cancelled' })
    renderPage()

    const cancelBtn = await screen.findByRole('button', { name: 'Cancel' })
    const resolveBtn = await screen.findByRole('button', {
      name: 'Resolve cancellation',
    })

    expect(cancelBtn).toBeInTheDocument()
    expect(resolveBtn).toBeInTheDocument()

    fireEvent.click(cancelBtn)
    await waitFor(() => expect(cancelJob).toHaveBeenCalledWith('job-r1'))

    fireEvent.click(resolveBtn)
    await waitFor(() => expect(resolveJob).toHaveBeenCalledWith('job-r2'))
  })

  it.each([
    ['Authentication failed. Please sign in again.', 'Sign in required.'],
    [
      'You do not have permission to view this resource.',
      'Permission required.',
    ],
  ])('maps %s to an actionable error title', (message, heading) => {
    expect(discoveryJobsErrorTitle(message)).toBe(heading)
  })
})
