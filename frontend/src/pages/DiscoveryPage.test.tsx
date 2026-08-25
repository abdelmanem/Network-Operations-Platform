import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  listTargets,
  listCredentialProfiles,
  createTarget,
  createJob,
  getJob,
  getDeviceResults,
  getEvidence,
  createCredentialProfile,
  testCredentialProfile,
} = vi.hoisted(() => ({
  listTargets: vi.fn(),
  listCredentialProfiles: vi.fn(),
  createTarget: vi.fn(),
  createJob: vi.fn(),
  getJob: vi.fn(),
  getDeviceResults: vi.fn(),
  getEvidence: vi.fn(),
  createCredentialProfile: vi.fn(),
  testCredentialProfile: vi.fn(),
}))

vi.mock('../api/discovery', () => ({
  listDiscoveryTargets: listTargets,
  listDiscoveryCredentialProfiles: listCredentialProfiles,
  createDiscoveryTarget: createTarget,
  createDiscoveryApiJob: createJob,
  getDiscoveryApiJob: getJob,
  getDiscoveryDeviceResults: getDeviceResults,
  getDiscoveryEvidence: getEvidence,
  createDiscoveryCredentialProfile: createCredentialProfile,
  testDiscoveryCredentialProfile: testCredentialProfile,
}))

import { DiscoveryPage } from './DiscoveryPage'

describe('DiscoveryPage', () => {
  beforeEach(() => {
    listTargets.mockReset()
    listCredentialProfiles.mockReset()
    createTarget.mockReset()
    createJob.mockReset()
    getJob.mockReset()
    getDeviceResults.mockReset()
    getEvidence.mockReset()
    createCredentialProfile.mockReset()
    testCredentialProfile.mockReset()
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
    listCredentialProfiles
      .mockResolvedValueOnce([])
      .mockResolvedValue([
        {
          profile_id: 'profile-cisco-ssh',
          tenant_id: 'default',
          name: 'Cisco Production SSH',
          description: 'Production Cisco access',
          transport_types: ['ssh'],
          provider_reference: 'cisco-prod',
          enabled: true,
          created_at: '2026-08-19T10:00:00Z',
          updated_at: '2026-08-19T10:00:00Z',
        },
      ])

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
    fireEvent.change(screen.getByLabelText(/secret reference/i), {
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
      expect(
        screen.getByText(/Environment secret provider/i),
      ).toBeInTheDocument()
      expect(
        screen.getByText(/This is not the password/i),
      ).toBeInTheDocument()
    })
  })

  it('hides the secret provider reference from the normal summary and reveals it in advanced details only', async () => {
    listTargets.mockResolvedValue([])
    listCredentialProfiles.mockResolvedValue([
      {
        profile_id: 'profile-cisco-ssh',
        tenant_id: 'default',
        name: 'Cisco Production SSH',
        description: 'Cisco SSH credentials',
        transport_types: ['ssh'],
        provider_reference: 'TEST_CISCO_SSH_PASSWORD',
        enabled: true,
        created_at: '2026-08-19T10:00:00Z',
        updated_at: '2026-08-19T10:00:00Z',
      },
    ])

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

    expect(screen.getByText('Secret')).toBeInTheDocument()
    expect(screen.getByText('Not tested')).toBeInTheDocument()
    expect(screen.queryByText('TEST_CISCO_SSH_PASSWORD')).not.toBeInTheDocument()

    const details = screen.getByText(/Advanced \/ Secret provider details/i)
    fireEvent.click(details)

    await waitFor(() => {
      expect(screen.getByText('Secret provider')).toBeInTheDocument()
      expect(screen.getByText('Environment')).toBeInTheDocument()
      expect(screen.getByText('Provider reference')).toBeInTheDocument()
      expect(screen.getByText('TEST_CISCO_SSH_PASSWORD')).toBeInTheDocument()
      expect(
        screen.getByText(/resolved by the backend at runtime and is never stored in or returned to the frontend/i),
      ).toBeInTheDocument()
    })
  })

  it.each([
    ['success', 'Credential profile resolved successfully for the selected transport.', 'Secret configured', 'Continue with device validation.'],
    ['invalid_credential_profile', 'Credential profile is enabled but no secret was resolved for its provider reference.', 'Secret missing', 'Configure the referenced secret before retrying.'],
    ['invalid_credential_profile', 'Credential type \'ssh_password\' is not compatible with transport \'ssh\'.', 'Invalid credential profile', 'Correct the profile configuration and retry.'],
    ['unsupported_transport', 'The requested transport is not supported by the credential execution boundary.', 'Unsupported transport', 'Select a supported transport/profile.'],
    ['success', 'Authentication failed: invalid credentials', 'Authentication failed', 'Verify the username and credential reference.'],
    ['success', 'Connection failed: host unreachable', 'Connection failed', 'Verify the device address and network reachability.'],
    ['success', 'Credential validation timed out after 30s', 'Timeout', 'Verify reachability and timeout conditions before retrying.'],
  ])(
    'maps backend result %s to the correct operator-facing status',
    async (status, message, expectedLabel, expectedAction) => {
      listTargets.mockResolvedValue([])
      listCredentialProfiles.mockResolvedValue([
        {
          profile_id: 'profile-cisco-ssh',
          tenant_id: 'default',
          name: 'Cisco Production SSH',
          description: 'Cisco SSH credentials',
          transport_types: ['ssh'],
          provider_reference: 'TEST_CISCO_SSH_PASSWORD',
          enabled: true,
          created_at: '2026-08-19T10:00:00Z',
          updated_at: '2026-08-19T10:00:00Z',
        },
      ])
      testCredentialProfile.mockResolvedValue({
        status,
        transport: 'ssh',
        target: '10.0.0.1',
        credential_type: 'ssh_password',
        message,
        provider_reference: 'TEST_CISCO_SSH_PASSWORD',
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

      fireEvent.click(screen.getAllByRole('button', { name: /test credential/i })[0])

      await waitFor(() => {
        expect(
          screen.getByText((_, element) => {
            return (
              element?.tagName === 'DIV' &&
              element.classList.contains('status-pill') &&
              element.textContent?.trim() === expectedLabel
            )
          }),
        ).toBeInTheDocument()
      })
      expect(
        screen.getByText((_, element) => {
          const text = element?.textContent?.replace(/\s+/g, ' ').trim()
          return text === `Next action: ${expectedAction}`
        }),
      ).toBeInTheDocument()
    },
  )

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
    getJob.mockResolvedValue({
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
    getDeviceResults.mockResolvedValue([])

    render(
      <MemoryRouter>
        <DiscoveryPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /add target/i }),
      ).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /add target/i }))

    fireEvent.change(screen.getByLabelText(/target name/i), {
      target: { value: 'switch-01' },
    })
    fireEvent.change(screen.getByLabelText(/management address/i), {
      target: { value: '10.0.0.1' },
    })
    fireEvent.change(
      screen.getByLabelText('Credential profile', {
        selector: '#add-target-credential-profile',
      }),
      {
        target: { value: 'profile-cisco-ssh' },
      },
    )
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

    fireEvent.click(screen.getAllByRole('button', { name: /start discovery/i })[0])
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

  it('labels collector metadata separately and shows the discovered device identity', async () => {
    listTargets.mockResolvedValue([
      {
        target_id: 'target-1',
        tenant_id: 'default',
        identifier: 'coreSW',
        address: '192.168.137.225',
        scope_type: 'single_device',
        scope_end: null,
        scope_cidr: null,
        credential_profile_id: 'profile-cisco-ssh',
        vendor: null,
        platform_hint: 'cisco-ios',
        preferred_transport: 'netmiko',
        enabled: true,
        created_at: '2026-08-19T10:00:00Z',
        updated_at: '2026-08-19T10:00:00Z',
      },
    ])
    listCredentialProfiles.mockResolvedValue([])
    createJob.mockResolvedValue({
      job_id: 'job-1',
      tenant_id: 'default',
      target_id: 'target-1',
      discovery_run_id: 'run-1',
      status: 'running',
      selected_transport: null,
      selected_platform: null,
      attempts: 0,
      error_code: null,
      error_message: null,
      created_at: '2026-08-19T10:00:00Z',
      queued_at: '2026-08-19T10:00:00Z',
      started_at: '2026-08-19T10:00:00Z',
      finished_at: null,
      timeout_seconds: 120,
      correlation_id: null,
    })
    getJob.mockResolvedValue({
      job_id: 'job-1',
      tenant_id: 'default',
      target_id: 'target-1',
      discovery_run_id: 'run-1',
      status: 'succeeded',
      selected_transport: 'netmiko',
      selected_platform: 'catalyst-2960',
      attempts: 1,
      error_code: null,
      error_message: null,
      created_at: '2026-08-19T10:00:00Z',
      queued_at: '2026-08-19T10:00:00Z',
      started_at: '2026-08-19T10:00:00Z',
      finished_at: '2026-08-19T10:00:01Z',
      timeout_seconds: 120,
      correlation_id: null,
    })
    getDeviceResults.mockResolvedValue([
      {
        result_id: 'result-1',
        address: '192.168.137.225',
        hostname: 'Radisson_Blu_BB',
        vendor: 'Cisco',
        model: 'WS-C4506-E',
        platform: 'ios',
        state: 'succeeded',
        selected_transport: 'netmiko',
        failure_code: null,
        failure_message: null,
        started_at: '2026-08-19T10:00:00Z',
        completed_at: '2026-08-19T10:00:01Z',
        correlation_id: null,
      },
    ])
    getEvidence.mockResolvedValue([])

    render(
      <MemoryRouter>
        <DiscoveryPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getAllByRole('button', { name: /start discovery/i })[1],
      ).toBeEnabled()
    })
    fireEvent.click(
      screen.getAllByRole('button', { name: /start discovery/i })[1],
    )

    await waitFor(
      () => {
        expect(screen.getByText('Collector family')).toBeInTheDocument()
        expect(screen.getByText('WS-C4506-E')).toBeInTheDocument()
        expect(screen.getByText('Radisson_Blu_BB')).toBeInTheDocument()
        expect(screen.getByText('ios')).toBeInTheDocument()
      },
      { timeout: 3000 },
    )
    expect(screen.getByText('catalyst-2960')).toBeInTheDocument()
    expect(screen.getByText('1 device discovered')).toBeInTheDocument()
  })

  it('displays accurate summary for CIDR discovery with succeeded and unavailable addresses', async () => {
    listTargets.mockResolvedValue([
      {
        target_id: 'target-cidr-1',
        tenant_id: 'default',
        identifier: 'Cisco SW 40',
        address: '192.168.40.0/24',
        scope_type: 'cidr_network',
        scope_end: null,
        scope_cidr: '192.168.40.0/24',
        credential_profile_id: 'profile-cisco-ssh',
        vendor: null,
        platform_hint: 'cisco-ios',
        preferred_transport: 'netmiko',
        enabled: true,
        created_at: '2026-08-19T10:00:00Z',
        updated_at: '2026-08-19T10:00:00Z',
      },
    ])
    listCredentialProfiles.mockResolvedValue([])
    createJob.mockResolvedValue({
      job_id: 'job-cidr-1',
      tenant_id: 'default',
      target_id: 'target-cidr-1',
      discovery_run_id: 'run-cidr-1',
      status: 'running',
      selected_transport: null,
      selected_platform: null,
      attempts: 0,
      error_code: null,
      error_message: null,
      created_at: '2026-08-19T10:00:00Z',
      queued_at: '2026-08-19T10:00:00Z',
      started_at: '2026-08-19T10:00:00Z',
      finished_at: null,
      timeout_seconds: 120,
      correlation_id: null,
    })
    getJob.mockResolvedValue({
      job_id: 'job-cidr-1',
      tenant_id: 'default',
      target_id: 'target-cidr-1',
      discovery_run_id: 'run-cidr-1',
      status: 'succeeded',
      selected_transport: 'netmiko',
      selected_platform: 'catalyst-2960',
      attempts: 1,
      error_code: null,
      error_message: null,
      created_at: '2026-08-19T10:00:00Z',
      queued_at: '2026-08-19T10:00:00Z',
      started_at: '2026-08-19T10:00:00Z',
      finished_at: '2026-08-19T10:00:25Z',
      timeout_seconds: 120,
      correlation_id: null,
    })

    const mockDeviceResults = [
      ...Array.from({ length: 9 }, (_, i) => ({
        result_id: `res-succ-${i}`,
        address: `192.168.40.${i + 1}`,
        hostname: `Switch-${i + 1}`,
        vendor: 'Cisco',
        model: 'WS-C2960X-24PS-L',
        platform: 'ios',
        state: 'succeeded',
        selected_transport: 'netmiko',
        failure_code: null,
        failure_message: null,
        started_at: '2026-08-19T10:00:00Z',
        completed_at: '2026-08-19T10:00:01Z',
        correlation_id: null,
      })),
      ...Array.from({ length: 245 }, (_, i) => ({
        result_id: `res-fail-${i}`,
        address: `192.168.40.${i + 10}`,
        hostname: null,
        vendor: null,
        model: null,
        platform: null,
        state: 'failed',
        selected_transport: null,
        failure_code: 'TRANSPORT_UNAVAILABLE',
        failure_message: 'TCP connection to device failed.',
        started_at: '2026-08-19T10:00:00Z',
        completed_at: '2026-08-19T10:00:01Z',
        correlation_id: null,
      })),
    ]

    getDeviceResults.mockResolvedValue(mockDeviceResults)
    getEvidence.mockResolvedValue([])

    render(
      <MemoryRouter>
        <DiscoveryPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getAllByRole('button', { name: /start discovery/i })[1],
      ).toBeEnabled()
    })
    fireEvent.click(
      screen.getAllByRole('button', { name: /start discovery/i })[1],
    )

    await waitFor(
      () => {
        expect(
          screen.getByText(
            '9 devices discovered (254 addresses scanned, 245 unavailable)',
          ),
        ).toBeInTheDocument()
      },
      { timeout: 3000 },
    )
  })
})
