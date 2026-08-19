import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { listTargets, createTarget, createJob, getJob, getEvidence } =
  vi.hoisted(() => ({
    listTargets: vi.fn(),
    createTarget: vi.fn(),
    createJob: vi.fn(),
    getJob: vi.fn(),
    getEvidence: vi.fn(),
  }))

vi.mock('../api/discovery', () => ({
  listDiscoveryTargets: listTargets,
  createDiscoveryTarget: createTarget,
  createDiscoveryApiJob: createJob,
  getDiscoveryApiJob: getJob,
  getDiscoveryEvidence: getEvidence,
}))

import { DiscoveryPage } from './DiscoveryPage'

describe('DiscoveryPage', () => {
  beforeEach(() => {
    listTargets.mockReset()
    createTarget.mockReset()
    createJob.mockReset()
    getJob.mockReset()
    getEvidence.mockReset()
  })

  it('renders an empty state when no discovery targets are available', async () => {
    listTargets.mockResolvedValue([])

    render(
      <MemoryRouter>
        <DiscoveryPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/no targets configured yet/i)).toBeInTheDocument()
    })
  })

  it('creates a target, starts a job, and displays terminal evidence', async () => {
    listTargets.mockResolvedValue([])
    createTarget.mockResolvedValue({
      target_id: 'target-1',
      tenant_id: 'default',
      identifier: 'switch-01',
      address: '10.0.0.1',
      scope_type: 'single_device',
      scope_end: null,
      scope_cidr: null,
      credential_profile_id: 'credential-profile:cisco-production',
      vendor: null,
      platform_hint: 'cisco-iosxe',
      preferred_transport: 'netmiko',
      enabled: true,
      created_at: '2026-08-19T10:00:00Z',
      updated_at: '2026-08-19T10:00:00Z',
    })
    createJob.mockResolvedValue({
      job_id: 'job-1',
      tenant_id: 'default',
      target_id: 'target-1',
      discovery_run_id: 'run-1',
      status: 'queued',
      selected_transport: null,
      selected_platform: null,
      attempts: 0,
      error_code: null,
      error_message: null,
      created_at: '2026-08-19T10:00:00Z',
      queued_at: '2026-08-19T10:00:00Z',
      started_at: null,
      finished_at: null,
      timeout_seconds: 120,
      correlation_id: null,
    })

    render(
      <MemoryRouter>
        <DiscoveryPage />
      </MemoryRouter>,
    )

    fireEvent.change(screen.getByLabelText(/target name/i), {
      target: { value: 'switch-01' },
    })
    fireEvent.change(screen.getByLabelText(/address/i), {
      target: { value: '10.0.0.1' },
    })
    fireEvent.change(screen.getByLabelText(/credential profile id/i), {
      target: { value: 'credential-profile:cisco-production' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save target/i }))

    await waitFor(() => {
      expect(createTarget).toHaveBeenCalledWith({
        identifier: 'switch-01',
        address: '10.0.0.1',
        scope_type: 'single_device',
        scope_end: null,
        scope_cidr: null,
        credential_profile_id: 'credential-profile:cisco-production',
        credential_references: {},
        allowed_fallback_transports: ['snmp', 'http'],
        platform_hint: 'cisco-iosxe',
        preferred_transport: 'netmiko',
        tenant_id: 'default',
        enabled: true,
        metadata: {},
      })
    })

    fireEvent.click(screen.getByRole('button', { name: /start discovery/i }))
    await waitFor(() => {
      expect(createJob).toHaveBeenCalledWith({
        target_id: 'target-1',
        requested_capabilities: { collector_name: 'cisco-ios-inventory' },
        metadata: { source: 'discovery-ui' },
        timeout_seconds: 120,
        correlation_id: expect.any(String),
      })
      expect(screen.getByText('queued')).toBeInTheDocument()
    })
  })
})
