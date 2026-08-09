import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { discoveryList, submitDiscoveryJob } = vi.hoisted(() => ({
  discoveryList: vi.fn(),
  submitDiscoveryJob: vi.fn(),
}))

vi.mock('../api/discovery', () => ({
  getDiscoveryRuns: discoveryList,
  submitDiscoveryJob,
}))

import { DiscoveryPage } from './DiscoveryPage'

describe('DiscoveryPage', () => {
  beforeEach(() => {
    discoveryList.mockReset()
    submitDiscoveryJob.mockReset()
  })

  it('renders an empty state when no discovery runs are available', async () => {
    discoveryList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, has_next: false })

    render(
      <MemoryRouter>
        <DiscoveryPage />
      </MemoryRouter>,
    )

    expect(screen.getByText(/loading discovery runs/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/no discovery runs have been created yet/i)).toBeInTheDocument()
    })
  })

  it('submits a discovery job and shows the new state', async () => {
    discoveryList
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 20, has_next: false })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'run-1',
            target_identifier: 'switch-01',
            target_address: '10.0.0.1',
            status: 'started',
            metadata: {},
            created_at: '2026-08-09T10:00:00Z',
            started_at: '2026-08-09T10:00:00Z',
            finished_at: null,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
        has_next: false,
      })

    submitDiscoveryJob.mockResolvedValue({ job_id: 'job-1', status: 'queued' })

    render(
      <MemoryRouter>
        <DiscoveryPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText(/target identifier/i), {
      target: { value: 'switch-01' },
    })
    fireEvent.change(screen.getByLabelText(/target address/i), {
      target: { value: '10.0.0.1' },
    })
    fireEvent.click(screen.getByRole('button', { name: /run discovery/i }))

    await waitFor(() => {
      expect(submitDiscoveryJob).toHaveBeenCalledWith({
        collector_contexts: [
          {
            target: {
              identifier: 'switch-01',
              address: '10.0.0.1',
              metadata: {},
            },
          },
        ],
        policies: [],
        metadata: {},
        priority: 0,
        timeout_seconds: null,
      })
    })

    await waitFor(() => {
      expect(screen.getByText(/discovery submitted/i)).toBeInTheDocument()
    })
  })
})
