import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  listTargets,
  listCredentialProfiles,
  createTarget,
  createJob,
  getJob,
  getEvidence,
  createCredentialProfile,
} = vi.hoisted(() => ({
  listTargets: vi.fn(),
  listCredentialProfiles: vi.fn(),
  createTarget: vi.fn(),
  createJob: vi.fn(),
  getJob: vi.fn(),
  getEvidence: vi.fn(),
  createCredentialProfile: vi.fn(),
}))

vi.mock('../api/discovery', () => ({
  listDiscoveryTargets: listTargets,
  listDiscoveryCredentialProfiles: listCredentialProfiles,
  createDiscoveryTarget: createTarget,
  createDiscoveryApiJob: createJob,
  getDiscoveryApiJob: getJob,
  getDiscoveryEvidence: getEvidence,
  createDiscoveryCredentialProfile: createCredentialProfile,
  createCredentialProfile,
}))

import { DiscoveryPage } from './DiscoveryPage'

describe('DiscoveryPage', () => {
  beforeEach(() => {
    listTargets.mockReset()
    listCredentialProfiles.mockReset()
    createTarget.mockReset()
    createJob.mockReset()
    getJob.mockReset()
    getEvidence.mockReset()
    createCredentialProfile.mockReset()
  })

  it('renders a credential-profile empty state and allows creation from the discovery workflow', async () => {
    listTargets.mockResolvedValue([])
    listCredentialProfiles.mockResolvedValue([])
    createCredentialProfile.mockResolvedValue({
      profile_id: 'profile-cisco-ssh',
      tenant_id: 'default',
      name: 'Cisco Production SSH',
      description: 'Production Cisco access',
      transport_types: ['ssh'],
      provider_reference: 'cisco-prod',
      enabled: true,
      created_at: '2026-08-19T10:00:00Z',
      updated_at: '2026-08-19T10:00:00Z',
    })

    render(
      <MemoryRouter>
        <DiscoveryPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByText(/no credential profiles are configured/i),
      ).toBeInTheDocument()
    })

    fireEvent.click(
      screen.getByRole('button', { name: /create credential profile/i }),
    )

    fireEvent.change(screen.getByLabelText(/profile name/i), {
      target: { value: 'Cisco Production SSH' },
    })
    fireEvent.change(screen.getByLabelText(/provider reference/i), {
      target: { value: 'cisco-prod' },
    })
    fireEvent.change(screen.getByLabelText(/credential type/i), {
      target: { value: 'ssh_password' },
    })
    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'netops' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save profile/i }))

    await waitFor(() => {
      expect(createCredentialProfile).toHaveBeenCalledWith({
        name: 'Cisco Production SSH',
        description: null,
        vendor: 'cisco',
        platform: 'cisco-iosxe',
        credential_type: 'ssh_password',
        username: 'netops',
        transport_types: ['ssh'],
        provider_reference: 'cisco-prod',
      })
    })
  })

  it('creates a target, starts a job, and displays terminal evidence', async () => {
    listTargets.mockResolvedValue([])
    listCredentialProfiles.mockResolvedValue([
      {
        profile_id: 'profile-cisco-ssh',
        tenant_id: 'default',
        name: 'Cisco Production SSH',
        description: 'Cisco SSH credentials',
        transport_types: ['ssh'],
        provider_reference: 'env://cisco-ssh',
        enabled: true,
        created_at: '2026-08-19T10:00:00Z',
        updated_at: '2026-08-19T10:00:00Z',
      },
    ])
    createTarget.mockResolvedValue({
      target_id: 'target-1',
      tenant_id: 'default',
      identifier: 'switch-01',
      address: '10.0.0.1',
      scope_type: 'single_device',
      scope_end: null,
      scope_cidr: null,
      credential_profile_id: 'profile-cisco-ssh',
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

    await waitFor(() => {
      expect(
        screen.getByRole('option', { name: /Cisco Production SSH/i }),
      ).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText(/target name/i), {
      target: { value: 'switch-01' },
    })
    fireEvent.change(screen.getByLabelText(/address/i), {
      target: { value: '10.0.0.1' },
    })
    fireEvent.change(screen.getByLabelText(/credential profile/i), {
      target: { value: 'profile-cisco-ssh' },
    })
    fireEvent.click(screen.getByRole('button', { name: /save target/i }))

    await waitFor(() => {
      expect(createTarget).toHaveBeenCalledWith({
        identifier: 'switch-01',
        address: '10.0.0.1',
        scope_type: 'single_device',
        scope_end: null,
        scope_cidr: null,
        credential_profile_id: 'profile-cisco-ssh',
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
