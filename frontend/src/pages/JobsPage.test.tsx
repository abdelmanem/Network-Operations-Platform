import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { discoveryJobsErrorTitle } from '../api/discovery'
import type { DiscoveryApiJobResponse } from '../types/api'

const { cancelJob, resolveJob, listJobs } = vi.hoisted(() => ({
  cancelJob: vi.fn(),
  resolveJob: vi.fn(),
  listJobs: vi.fn(),
}))

vi.mock('../api/discovery', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/discovery')>()),
  cancelDiscoveryApiJob: cancelJob,
  resolveDiscoveryApiJobCancellation: resolveJob,
  listDiscoveryApiJobs: listJobs,
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
    discovery_run_id: null,
    status,
    selected_transport: 'netmiko',
    selected_platform: 'cisco-iosxe',
    attempts: 1,
    error_code: status === 'failed' ? 'connection_failed' : null,
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

function response(items = [job('succeeded')], page = 1, hasNext = false) {
  return {
    items,
    page,
    page_size: 20,
    total: items.length + (hasNext ? 20 : 0),
    has_next: hasNext,
  }
}

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
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => vi.useRealTimers())

  it('renders a durable persisted discovery job even when the legacy repository is not used', async () => {
    listJobs.mockResolvedValue(response([job('succeeded')]))
    renderPage()

    expect(await screen.findByText('job-succeeded')).toBeInTheDocument()
    expect(listJobs).toHaveBeenCalledWith(1, 20)
    expect(screen.getByText('succeeded')).toBeInTheDocument()
    expect(screen.getByText('target-succeeded')).toBeInTheDocument()
  })

  it('renders queued, running, succeeded, and failed states with failure details', async () => {
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

  it('renders a true empty state', async () => {
    listJobs.mockResolvedValue(response([]))
    renderPage()
    expect(
      await screen.findByText(/no discovery jobs have been created yet/i),
    ).toBeInTheDocument()
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

  it('supports durable API pagination and manual refresh', async () => {
    listJobs
      .mockResolvedValueOnce(response([job('succeeded', 'first')], 1, true))
      .mockResolvedValueOnce(response([job('failed', 'second')], 2))
      .mockResolvedValueOnce(response([job('failed', 'second')], 2))
    renderPage()

    expect(await screen.findByText('job-first')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(await screen.findByText('job-second')).toBeInTheDocument()
    expect(listJobs).toHaveBeenLastCalledWith(2, 20)

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(listJobs).toHaveBeenCalledTimes(3))
  })

  it('polls active jobs and stops after they become terminal', async () => {
    vi.useFakeTimers()
    listJobs
      .mockResolvedValueOnce(response([job('running')]))
      .mockResolvedValueOnce(response([job('succeeded')]))
    renderPage()

    await act(async () => {
      await Promise.resolve()
    })
    expect(listJobs).toHaveBeenCalledTimes(1)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(listJobs).toHaveBeenCalledTimes(2)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000)
    })
    expect(listJobs).toHaveBeenCalledTimes(2)
  })

  it('links to the existing discovery detail UI for evidence and device results', async () => {
    listJobs.mockResolvedValue(response([job('succeeded', 'detail')]))
    renderPage()
    const link = await screen.findByRole('link', { name: /view details/i })
    expect(link).toHaveAttribute('href', '/discovery?job_id=job-detail')
  })

  it('shows Cancel only for active jobs and requests cooperative cancellation', async () => {
    listJobs
      .mockResolvedValueOnce(response([job('queued'), job('running'), job('succeeded')]))
      .mockResolvedValueOnce(
        response([
          { ...job('queued'), cancellation_requested_at: '2026-08-09T10:01:30Z' },
          job('running'),
          job('succeeded'),
        ]),
      )
    cancelJob.mockResolvedValue({ ...job('queued'), status: 'cancelled' })
    renderPage()

    const cancelButtons = await screen.findAllByRole('button', { name: 'Cancel' })
    expect(cancelButtons).toHaveLength(2)
    fireEvent.click(cancelButtons[0])

    await waitFor(() =>
      expect(cancelJob).toHaveBeenCalledWith('job-queued'),
    )
    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringMatching(/in-flight network I\/O may finish or time out/i),
    )
  })

  it('does not submit a cancellation request when the confirmation is declined', async () => {
    vi.mocked(window.confirm).mockReturnValue(false)
    listJobs.mockResolvedValue(response([job('running')]))
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(cancelJob).not.toHaveBeenCalled()
  })

  it('shows a cancellation API error instead of an empty state', async () => {
    listJobs.mockResolvedValue(response([job('running')]))
    cancelJob.mockRejectedValue(new Error('Permission denied.'))
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Permission required.')
  })

  it('shows Cancellation requested… disabled when a healthy job with active worker lease has cancellation requested', async () => {
    listJobs.mockResolvedValue(
      response([
        {
          ...job('running'),
          cancellation_requested_at: '2026-08-09T10:01:30Z',
          has_active_lease: true,
          execution_owner: 'owner-uuid',
          lease_expires_at: '2099-01-01T00:00:00Z',
        },
      ]),
    )
    renderPage()

    const button = await screen.findByRole('button', {
      name: 'Cancellation requested…',
    })
    expect(button).toBeInTheDocument()
    expect(button).toBeDisabled()
  })

  it('shows Resolve cancellation for a cancellation-requested job with no active worker lease', async () => {
    listJobs.mockResolvedValue(
      response([
        {
          ...job('running', 'stale-cancelled'),
          cancellation_requested_at: '2026-08-09T10:01:30Z',
          has_active_lease: false,
          execution_owner: null,
          lease_expires_at: null,
        },
      ]),
    )
    resolveJob.mockResolvedValue({
      ...job('running', 'stale-cancelled'),
      status: 'cancelled',
    })
    renderPage()

    const resolveBtn = await screen.findByRole('button', {
      name: 'Resolve cancellation',
    })
    expect(resolveBtn).toBeInTheDocument()
    expect(resolveBtn).not.toBeDisabled()

    fireEvent.click(resolveBtn)

    await waitFor(() =>
      expect(resolveJob).toHaveBeenCalledWith('job-stale-cancelled'),
    )
    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringMatching(/does not terminate active network I\/O/i),
    )
  })

  it('does not resolve cancellation when operator declines confirmation prompt', async () => {
    vi.mocked(window.confirm).mockReturnValue(false)
    listJobs.mockResolvedValue(
      response([
        {
          ...job('running', 'declined'),
          cancellation_requested_at: '2026-08-09T10:01:30Z',
          has_active_lease: false,
        },
      ]),
    )
    renderPage()

    const resolveBtn = await screen.findByRole('button', {
      name: 'Resolve cancellation',
    })
    fireEvent.click(resolveBtn)
    expect(resolveJob).not.toHaveBeenCalled()
  })

  it('shows no action for terminal jobs (succeeded, cancelled, failed)', async () => {
    listJobs.mockResolvedValue(
      response([
        job('succeeded', 's1'),
        { ...job('failed', 'c1'), status: 'cancelled' },
        job('failed', 'f1'),
      ]),
    )
    renderPage()

    await screen.findByText('job-s1')
    expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Resolve cancellation' })).toBeNull()
  })
})
