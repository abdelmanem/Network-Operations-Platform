import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SettingsPage } from '../pages/SettingsPage'
import type { NetBoxIntegrationStatusResponse } from '../types/api'
import { AuthContext } from '../lib/auth'
import axios from 'axios'

const { mockGetNetBoxStatus, mockTestNetBoxConnection, mockSyncNetBoxInventory } = vi.hoisted(() => ({
  mockGetNetBoxStatus: vi.fn(),
  mockTestNetBoxConnection: vi.fn(),
  mockSyncNetBoxInventory: vi.fn(),
}))

vi.mock('../api/integrations', () => ({
  getNetBoxStatus: mockGetNetBoxStatus,
  testNetBoxConnection: mockTestNetBoxConnection,
  syncNetBoxInventory: mockSyncNetBoxInventory,
}))

function makeStatus(overrides: Partial<NetBoxIntegrationStatusResponse> = {}): NetBoxIntegrationStatusResponse {
  return {
    configured: true,
    connected: true,
    tls_verified: true,
    authenticated: true,
    version: '4.6.8',
    hostname: 'caizhnetbok01',
    last_successful_sync: '2026-08-17T10:57:35Z',
    current_sync_status: 'idle',
    sync_started_at: null,
    sync_completed_at: null,
    sync_error: null,
    inventory_counts: {
      devices: 1641,
      interfaces: 5329,
      ip_addresses: 935,
      vlans: 31,
    },
    ...overrides,
  }
}

describe('SettingsPage - NetBox Integration', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  const renderWithAuth = (ui: React.ReactElement, permissions: string[] = ['inventory:write']) => {
    const authContextValue = {
      user: { username: 'testuser', email: 'test@example.com', roles: ['admin'], permissions },
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      status: 'ready' as const,
    }
    return render(
      <AuthContext.Provider value={authContextValue}>
        <MemoryRouter>{ui}</MemoryRouter>
      </AuthContext.Provider>
    )
  }

  it('renders loading state initially', async () => {
    mockGetNetBoxStatus.mockReturnValue(new Promise(() => {}))
    renderWithAuth(<SettingsPage />)
    expect(screen.getByText(/Loading configuration/i)).toBeInTheDocument()
  })

  it('renders NetBox status and inventory counts when loaded', async () => {
    mockGetNetBoxStatus.mockResolvedValue(makeStatus())
    renderWithAuth(<SettingsPage />)

    await waitFor(() => {
      expect(screen.queryByText(/Loading configuration/i)).not.toBeInTheDocument()
    })

    expect(screen.getByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('4.6.8')).toBeInTheDocument()
    expect(screen.getByText('caizhnetbok01')).toBeInTheDocument()
    expect(screen.getByText('1,641')).toBeInTheDocument()
    expect(screen.getByText('5,329')).toBeInTheDocument()
    expect(screen.getByText('935')).toBeInTheDocument()
    expect(screen.getByText('31')).toBeInTheDocument()
  })

  it('disables actions and shows read-only text if user lacks inventory:write permission', async () => {
    mockGetNetBoxStatus.mockResolvedValue(makeStatus())
    renderWithAuth(<SettingsPage />, ['inventory:read'])

    await screen.findByText('Connected')

    const testBtn = screen.getByRole('button', { name: /Test NetBox Connection/i })
    const syncBtn = screen.getByRole('button', { name: /Synchronize Inventory/i })

    expect(testBtn).toBeDisabled()
    expect(syncBtn).toBeDisabled()
    expect(screen.getByText(/Read-only access/i)).toBeInTheDocument()
  })

  it('enables action buttons if user has inventory:write permission', async () => {
    mockGetNetBoxStatus.mockResolvedValue(makeStatus())
    renderWithAuth(<SettingsPage />, ['inventory:write'])

    await screen.findByText('Connected')

    const testBtn = screen.getByRole('button', { name: /Test NetBox Connection/i })
    const syncBtn = screen.getByRole('button', { name: /Synchronize Inventory/i })

    expect(testBtn).not.toBeDisabled()
    expect(syncBtn).not.toBeDisabled()
  })

  it('triggers connection test and displays diagnostic result', async () => {
    mockGetNetBoxStatus.mockResolvedValue(makeStatus())
    mockTestNetBoxConnection.mockResolvedValue({
      connected: true,
      tls_verified: true,
      authenticated: true,
      version: '4.6.8',
      hostname: 'caizhnetbok01',
      message: 'NetBox connection check successful.',
    })

    renderWithAuth(<SettingsPage />)
    await screen.findByText('Connected')

    const testBtn = screen.getByRole('button', { name: /Test NetBox Connection/i })
    fireEvent.click(testBtn)

    await screen.findByText(/✓ NetBox connection check successful/i)
  })

  it('triggers connection test and displays error message on failure', async () => {
    mockGetNetBoxStatus.mockResolvedValue(makeStatus())
    const axiosError = {
      isAxiosError: true,
      response: {
        data: {
          code: 'NETBOX_TLS_VALIDATION_FAILED',
          message: 'NetBox TLS certificate validation failed.',
        },
      },
    }
    mockTestNetBoxConnection.mockRejectedValue(axiosError)

    // Stub axios.isAxiosError behavior for testing-library
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)

    renderWithAuth(<SettingsPage />)
    await screen.findByText('Connected')

    const testBtn = screen.getByRole('button', { name: /Test NetBox Connection/i })
    fireEvent.click(testBtn)

    await screen.findByText(/NetBox TLS certificate validation failed/i)
  })

  it('shows running status during synchronization and polls progress', async () => {
    // Initial load returns running state
    mockGetNetBoxStatus.mockResolvedValueOnce(makeStatus({ current_sync_status: 'running' }))
    // Second call (polling) returns succeeded state
    mockGetNetBoxStatus.mockResolvedValueOnce(makeStatus({ current_sync_status: 'succeeded' }))

    renderWithAuth(<SettingsPage />)
    await screen.findByText(/running/i)

    await waitFor(() => {
      expect(screen.getByText(/succeeded/i)).toBeInTheDocument()
    }, { timeout: 3500 })
  })
})
