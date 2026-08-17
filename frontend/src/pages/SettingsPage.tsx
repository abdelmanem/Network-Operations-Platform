import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'
import {
  getNetBoxStatus,
  testNetBoxConnection,
  syncNetBoxInventory,
} from '../api/integrations'
import type { NetBoxIntegrationStatusResponse } from '../types/api'
import axios from 'axios'

export function SettingsPage() {
  const { user } = useAuth()
  const [statusData, setStatusData] = useState<NetBoxIntegrationStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Actions states
  const [testingConnection, setTestingConnection] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testError, setTestError] = useState<string | null>(null)
  const [syncingInventory, setSyncingInventory] = useState(false)
  const [syncMessage, setSyncMessage] = useState<string | null>(null)

  // Enforce frontend permission check (UX only)
  const hasWritePermission = user?.permissions?.includes('inventory:write') ?? false

  const fetchStatus = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setError(null)
    try {
      const data = await getNetBoxStatus()
      setStatusData(data)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data?.message) {
        setError(err.response.data.message)
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load NetBox status.')
      }
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  // Poll status silently if sync job is active
  useEffect(() => {
    void fetchStatus()
  }, [fetchStatus])

  useEffect(() => {
    let intervalId: any
    const isSyncActive =
      statusData?.current_sync_status === 'queued' ||
      statusData?.current_sync_status === 'running'

    if (isSyncActive) {
      intervalId = setInterval(() => {
        void fetchStatus(true)
      }, 1500)
    }

    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }, [statusData?.current_sync_status, fetchStatus])

  const handleTestConnection = async () => {
    if (testingConnection) return
    setTestingConnection(true)
    setTestResult(null)
    setTestError(null)

    try {
      const resp = await testNetBoxConnection()
      setTestResult(resp.message || 'Connection test successful.')
      // Refresh status details
      void fetchStatus(true)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data?.message) {
        setTestError(`${err.response.data.message} (Code: ${err.response.data.code})`)
      } else {
        setTestError(err instanceof Error ? err.message : 'Connection test failed.')
      }
    } finally {
      setTestingConnection(false)
    }
  }

  const handleSyncInventory = async () => {
    if (syncingInventory) return
    setSyncingInventory(true)
    setSyncMessage(null)

    try {
      await syncNetBoxInventory()
      setSyncMessage('Synchronization request submitted. Monitoring progress...')
      // Trigger status refresh to transition state to 'queued'/'running'
      void fetchStatus(true)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data?.message) {
        setSyncMessage(`Sync failed: ${err.response.data.message}`)
      } else {
        setSyncMessage(err instanceof Error ? err.message : 'Failed to start synchronization.')
      }
    } finally {
      setSyncingInventory(false)
    }
  }

  if (loading) {
    return (
      <div className="page" style={{ padding: '2rem' }}>
        <h2>Settings</h2>
        <p className="muted">Loading configuration and NetBox integration status…</p>
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <div className="loading-state">Loading application…</div>
        </div>
      </div>
    )
  }

  return (
    <div className="page" style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto' }}>
      <h2>Settings</h2>
      <p className="muted">Application configuration and third-party integration settings.</p>

      {error && (
        <div className="card" style={{ borderLeft: '4px solid #ef4444', background: 'rgba(239, 68, 68, 0.05)', marginBottom: '1.5rem' }}>
          <h4 style={{ color: '#ef4444', margin: '0 0 0.5rem 0' }}>Configuration Error</h4>
          <p style={{ margin: 0 }}>{error}</p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '2rem', marginTop: '2rem' }}>
        
        {/* NetBox Integration Section */}
        <section className="card" style={{ padding: '2rem', background: 'rgba(30, 41, 59, 0.4)', borderRadius: '0.75rem', border: '1px solid rgba(148, 163, 184, 0.2)' }}>
          <h3 style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.1)', paddingBottom: '0.75rem', marginTop: 0 }}>NetBox Integration</h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '2rem', marginTop: '1.5rem' }}>
            
            {/* Connection Status Column */}
            <div>
              <h4 style={{ color: '#94a3b8', marginBottom: '1rem' }}>Connection & Security</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Connection:</span>
                  <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ color: statusData?.connected ? '#22c55e' : '#ef4444' }}>●</span>
                    {statusData?.connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>TLS Verification:</span>
                  <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ color: statusData?.tls_verified ? '#22c55e' : '#ef4444' }}>●</span>
                    {statusData?.tls_verified ? 'Verified' : 'Unverified'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Authentication:</span>
                  <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ color: statusData?.authenticated ? '#22c55e' : '#ef4444' }}>●</span>
                    {statusData?.authenticated ? 'Successful' : 'Failed'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(148, 163, 184, 0.1)', paddingTop: '0.5rem' }}>
                  <span className="muted">Version:</span>
                  <span style={{ fontFamily: 'monospace' }}>{statusData?.version || 'Unknown'}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="muted">Hostname:</span>
                  <span style={{ fontFamily: 'monospace' }}>{statusData?.hostname || 'Unknown'}</span>
                </div>
              </div>
            </div>

            {/* Sync Status Column */}
            <div>
              <h4 style={{ color: '#94a3b8', marginBottom: '1rem' }}>Synchronization</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Sync Status:</span>
                  <span style={{
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    fontSize: '0.85rem',
                    padding: '0.2rem 0.5rem',
                    borderRadius: '0.25rem',
                    background:
                      statusData?.current_sync_status === 'running' ? 'rgba(59, 130, 246, 0.2)' :
                      statusData?.current_sync_status === 'queued' ? 'rgba(234, 179, 8, 0.2)' :
                      statusData?.current_sync_status === 'succeeded' ? 'rgba(34, 197, 94, 0.2)' :
                      statusData?.current_sync_status === 'failed' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(148, 163, 184, 0.2)',
                    color:
                      statusData?.current_sync_status === 'running' ? '#3b82f6' :
                      statusData?.current_sync_status === 'queued' ? '#eab308' :
                      statusData?.current_sync_status === 'succeeded' ? '#22c55e' :
                      statusData?.current_sync_status === 'failed' ? '#ef4444' : '#94a3b8'
                  }}>
                    {statusData?.current_sync_status || 'idle'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="muted">Last Successful Sync:</span>
                  <span style={{ fontSize: '0.9rem' }}>
                    {statusData?.last_successful_sync
                      ? new Date(statusData.last_successful_sync).toLocaleString()
                      : 'Never'}
                  </span>
                </div>
                {statusData?.sync_error && (
                  <div style={{ borderTop: '1px solid rgba(148, 163, 184, 0.1)', paddingTop: '0.5rem' }}>
                    <span className="muted" style={{ display: 'block', fontSize: '0.85rem' }}>Last Failure:</span>
                    <span style={{ color: '#ef4444', fontSize: '0.85rem', wordBreak: 'break-all' }}>{statusData.sync_error}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Inventory Counts Column */}
            <div>
              <h4 style={{ color: '#94a3b8', marginBottom: '1rem' }}>Persisted Expected Inventory</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ background: 'rgba(15, 23, 42, 0.3)', padding: '0.75rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span className="muted" style={{ display: 'block', fontSize: '0.8rem' }}>Devices</span>
                  <strong style={{ fontSize: '1.25rem', color: '#eff6ff' }}>
                    {statusData?.inventory_counts?.devices?.toLocaleString() ?? 0}
                  </strong>
                </div>
                <div style={{ background: 'rgba(15, 23, 42, 0.3)', padding: '0.75rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span className="muted" style={{ display: 'block', fontSize: '0.8rem' }}>Interfaces</span>
                  <strong style={{ fontSize: '1.25rem', color: '#eff6ff' }}>
                    {statusData?.inventory_counts?.interfaces?.toLocaleString() ?? 0}
                  </strong>
                </div>
                <div style={{ background: 'rgba(15, 23, 42, 0.3)', padding: '0.75rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span className="muted" style={{ display: 'block', fontSize: '0.8rem' }}>IP Addresses</span>
                  <strong style={{ fontSize: '1.25rem', color: '#eff6ff' }}>
                    {statusData?.inventory_counts?.ip_addresses?.toLocaleString() ?? 0}
                  </strong>
                </div>
                <div style={{ background: 'rgba(15, 23, 42, 0.3)', padding: '0.75rem', borderRadius: '0.5rem', textAlign: 'center' }}>
                  <span className="muted" style={{ display: 'block', fontSize: '0.8rem' }}>VLANs</span>
                  <strong style={{ fontSize: '1.25rem', color: '#eff6ff' }}>
                    {statusData?.inventory_counts?.vlans?.toLocaleString() ?? 0}
                  </strong>
                </div>
              </div>
            </div>

          </div>

          {/* Action Row */}
          <div style={{ borderTop: '1px solid rgba(148, 163, 184, 0.1)', marginTop: '2rem', paddingTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testingConnection || syncingInventory || !hasWritePermission || statusData?.current_sync_status === 'running'}
                style={{
                  background: 'transparent',
                  border: '1px solid #3b82f6',
                  color: '#3b82f6',
                  padding: '0.6rem 1.2rem',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}
              >
                {testingConnection ? 'Testing…' : 'Test NetBox Connection'}
              </button>

              <button
                type="button"
                onClick={handleSyncInventory}
                disabled={testingConnection || syncingInventory || !hasWritePermission || statusData?.current_sync_status === 'running' || statusData?.current_sync_status === 'queued'}
                style={{
                  background: '#3b82f6',
                  border: 'none',
                  color: '#eff6ff',
                  padding: '0.6rem 1.2rem',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}
              >
                {statusData?.current_sync_status === 'running' || statusData?.current_sync_status === 'queued' ? 'Synchronizing…' : 'Synchronize Inventory'}
              </button>
            </div>

            {/* Diagnostic results or helper logs */}
            {testResult && (
              <p style={{ color: '#22c55e', margin: 0, fontSize: '0.9rem' }}>✓ {testResult}</p>
            )}
            {testError && (
              <div style={{ background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '0.75rem', borderRadius: '0.375rem' }}>
                <p style={{ color: '#ef4444', margin: 0, fontSize: '0.9rem', fontWeight: 600 }}>Connection Test Failed</p>
                <p style={{ color: '#f3f4f6', margin: '0.25rem 0 0 0', fontSize: '0.85rem' }}>{testError}</p>
              </div>
            )}
            {syncMessage && (
              <p style={{ color: '#eab308', margin: 0, fontSize: '0.9rem' }}>ℹ {syncMessage}</p>
            )}

            {!hasWritePermission && (
              <span className="muted" style={{ fontSize: '0.85rem', fontStyle: 'italic' }}>
                Read-only access: You do not have permission to test connection or run synchronization.
              </span>
            )}
          </div>
        </section>

        {/* Other Application details card */}
        <section className="card" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', background: 'rgba(30, 41, 59, 0.2)', padding: '1.5rem', borderRadius: '0.75rem', border: '1px solid rgba(148, 163, 184, 0.1)' }}>
          <div>
            <h4 style={{ margin: '0 0 0.5rem 0', color: '#94a3b8' }}>API Base URL</h4>
            <p style={{ margin: 0, fontFamily: 'monospace' }}>
              {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}
            </p>
          </div>
          <div>
            <h4 style={{ margin: '0 0 0.5rem 0', color: '#94a3b8' }}>Authentication</h4>
            <p style={{ margin: 0 }}>Bearer token stored in browser local storage.</p>
          </div>
        </section>

      </div>
    </div>
  )
}
