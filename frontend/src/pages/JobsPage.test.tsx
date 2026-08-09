import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { jobsList, getJob } = vi.hoisted(() => ({
  jobsList: vi.fn(),
  getJob: vi.fn(),
}))

vi.mock('../api/jobs', () => ({
  getJobs: jobsList,
  getJob,
}))

import { JobsPage } from './JobsPage'

describe('JobsPage', () => {
  beforeEach(() => {
    jobsList.mockReset()
    getJob.mockReset()
  })

  it('renders an empty state when no jobs are available', async () => {
    jobsList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, has_next: false })

    render(
      <MemoryRouter>
        <JobsPage />
      </MemoryRouter>,
    )

    expect(screen.getByText(/loading jobs/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/no jobs have been created yet/i)).toBeInTheDocument()
    })
  })

  it('shows job status and progress for a running job', async () => {
    jobsList.mockResolvedValue({
      items: [
        {
          job_id: 'job-1',
          status: 'running',
          message: 'Collecting inventory',
          created_at: '2026-08-09T10:00:00Z',
          updated_at: '2026-08-09T10:02:00Z',
          attempts: 1,
          progress: 45,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      has_next: false,
    })

    render(
      <MemoryRouter>
        <JobsPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('running')).toBeInTheDocument()
      expect(screen.getByText('45%')).toBeInTheDocument()
    })
  })
})
