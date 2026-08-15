import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../components/dashboard/EmptyState'
import { ErrorState } from '../components/dashboard/ErrorState'
import { KpiCard } from '../components/dashboard/KpiCard'
import { compareDevice } from '../api/devices'
import {
  listLiveInventory,
  listNetboxInventory,
} from '../api/inventory'
import { getSnapshot, listDeviceInterfaces, listDeviceNeighbors, listDeviceVlans } from '../api/snapshots'
import type {
  DeviceComparisonResponse,
  InterfaceListResponse,
  InventoryListResponse,
  NeighborListResponse,
  SnapshotResponse,
  VlanListResponse,
} from '../types/api'

type PageSection = 'overview' | 'expected' | 'live' | 'variance' | 'comparison' | 'detail'
type DetailView = 'interfaces' | 'vlans' | 'neighbors' | null

interface LoadState {
  state: 'loading' | 'ready' | 'empty' | 'error'
  error?: string
}

export function NetworkPage() {
  // Main state
  const [currentSection, setCurrentSection] = useState<PageSection>('overview')
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  const [detailView, setDetailView] = useState<DetailView>(null)

  // Inventory data
  const [netboxInventory, setNetboxInventory] = useState<InventoryListResponse | null>(null)
  const [liveInventory, setLiveInventory] = useState<InventoryListResponse | null>(null)
  const [netboxPage, setNetboxPage] = useState(1)
  const [livePage, setLivePage] = useState(1)

  // Comparison data
  const [comparison, setComparison] = useState<DeviceComparisonResponse | null>(null)

  // Detail data
  const [detailSnapshot, setDetailSnapshot] = useState<SnapshotResponse | null>(null)
  const [detailInterfaces, setDetailInterfaces] = useState<InterfaceListResponse | null>(null)
  const [detailVlans, setDetailVlans] = useState<VlanListResponse | null>(null)
  const [detailNeighbors, setDetailNeighbors] = useState<NeighborListResponse | null>(null)

  // Load states
  const [netboxState, setNetboxState] = useState<LoadState>({ state: 'loading' })
  const [liveState, setLiveState] = useState<LoadState>({ state: 'loading' })
  const [comparisonState, setComparisonState] = useState<LoadState>({ state: 'loading' })
  const [detailState, setDetailState] = useState<LoadState>({ state: 'loading' })

  // Load NetBox inventory
  const loadNetboxInventory = useCallback(
    async (page: number = 1) => {
      setNetboxState({ state: 'loading' })
      try {
        const data = await listNetboxInventory(page, 50)
        setNetboxInventory(data)
        setNetboxPage(page)
        setNetboxState({ state: data.items.length === 0 ? 'empty' : 'ready' })
      } catch (err) {
        setNetboxState({
          state: 'error',
          error: err instanceof Error ? err.message : 'Failed to load NetBox inventory',
        })
      }
    },
    [],
  )

  // Load live inventory
  const loadLiveInventory = useCallback(
    async (page: number = 1) => {
      setLiveState({ state: 'loading' })
      try {
        const data = await listLiveInventory(page, 50)
        setLiveInventory(data)
        setLivePage(page)
        setLiveState({ state: data.items.length === 0 ? 'empty' : 'ready' })
      } catch (err) {
        setLiveState({
          state: 'error',
          error: err instanceof Error ? err.message : 'Failed to load live inventory',
        })
      }
    },
    [],
  )

  // Load device comparison
  const loadComparison = useCallback(
    async (deviceId: string) => {
      setComparisonState({ state: 'loading' })
      try {
        const data = await compareDevice(deviceId)
        setComparison(data)
        setSelectedDeviceId(deviceId)
        setCurrentSection('comparison')
        setComparisonState({ state: 'ready' })
      } catch (err) {
        setComparisonState({
          state: 'error',
          error: err instanceof Error ? err.message : 'Failed to load device comparison',
        })
      }
    },
    [],
  )

  // Load device detail
  const loadDeviceDetail = useCallback(
    async (snapshotId: string, deviceId: string, view: DetailView) => {
      setDetailState({ state: 'loading' })
      try {
        const snapshot = await getSnapshot(snapshotId)
        setDetailSnapshot(snapshot)

        if (view === 'interfaces') {
          const interfaces = await listDeviceInterfaces(snapshotId, deviceId)
          setDetailInterfaces(interfaces)
        } else if (view === 'vlans') {
          const vlans = await listDeviceVlans(snapshotId, deviceId)
          setDetailVlans(vlans)
        } else if (view === 'neighbors') {
          const neighbors = await listDeviceNeighbors(snapshotId, deviceId)
          setDetailNeighbors(neighbors)
        }

        setDetailView(view)
        setCurrentSection('detail')
        setDetailState({ state: 'ready' })
      } catch (err) {
        setDetailState({
          state: 'error',
          error: err instanceof Error ? err.message : 'Failed to load device details',
        })
      }
    },
    [],
  )

  // Initial load
  useEffect(() => {
    void loadNetboxInventory(1)
    void loadLiveInventory(1)
  }, [loadNetboxInventory, loadLiveInventory])

  // Compute variance summary
  const varianceSummary = useMemo(() => {
    if (!netboxInventory || !liveInventory) return null

    const netboxIds = new Set(netboxInventory.items.map((d) => d.device_id))
    const liveIds = new Set(liveInventory.items.map((d) => d.device_id))

    const missing = Array.from(netboxIds).filter((id) => !liveIds.has(id)).length
    const unexpected = Array.from(liveIds).filter((id) => !netboxIds.has(id)).length
    const common = Array.from(netboxIds).filter((id) => liveIds.has(id)).length

    return {
      missing,
      unexpected,
      common,
      total: netboxInventory.device_count + liveInventory.device_count,
    }
  }, [netboxInventory, liveInventory])

  // Handle device selection from inventory
  const handleSelectDevice = (deviceId: string) => {
    void loadComparison(deviceId)
  }

  // Format timestamp for display
  const formatTimestamp = (ts: string | null) => {
    if (!ts) return 'Unknown'
    try {
      return new Date(ts).toLocaleString()
    } catch {
      return ts
    }
  }

  // RENDER: Overview Section
  // =========================================================================
  const renderOverview = () => (
    <div className="card">
      <h2>Network Operations Overview</h2>
      <p className="muted">
        Expected state (NetBox) vs Observed state (Live Discovery)
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1.5rem' }}>
        <KpiCard
          title="Expected Devices"
          value={netboxInventory?.device_count}
          unit={null}
          description="Devices in NetBox"
        />
        <KpiCard
          title="Observed Devices"
          value={liveInventory?.device_count}
          unit={null}
          description="Devices discovered"
        />
        <KpiCard
          title="Missing"
          value={varianceSummary?.missing}
          unit={null}
          description="In NetBox, not discovered"
        />
        <KpiCard
          title="Unexpected"
          value={varianceSummary?.unexpected}
          unit={null}
          description="Discovered, not in NetBox"
        />
      </div>

      {netboxInventory && (
        <div style={{ marginTop: '1rem', fontSize: '0.875rem', color: '#666' }}>
          <p>
            <strong>Expected State:</strong> {formatTimestamp(netboxInventory.snapshot_captured_at)} (Source: {netboxInventory.source})
          </p>
        </div>
      )}

      {liveInventory && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.875rem', color: '#666' }}>
          <p>
            <strong>Observed State:</strong> {formatTimestamp(liveInventory.snapshot_captured_at)} (Source: {liveInventory.source})
          </p>
        </div>
      )}

      <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
        <button
          type="button"
          onClick={() => setCurrentSection('expected')}
          style={{ padding: '0.5rem 1rem' }}
        >
          View Expected Inventory →
        </button>
        <button
          type="button"
          onClick={() => setCurrentSection('live')}
          style={{ padding: '0.5rem 1rem' }}
        >
          View Live Inventory →
        </button>
      </div>

      <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: '#f5f5f5', borderRadius: '4px' }}>
        <h3>Discovery & Jobs</h3>
        <p className="muted">Manage network discovery runs and view job status.</p>
        <Link to="/discovery" style={{ marginRight: '1rem' }}>
          View Discovery →
        </Link>
        <Link to="/jobs">View Jobs →</Link>
      </div>
    </div>
  )

  // =========================================================================
  // RENDER: Expected Inventory (NetBox)
  // =========================================================================
  const renderExpectedInventory = () => {
    if (netboxState.state === 'loading') {
      return <EmptyState title="Loading" message="Loading NetBox inventory…" />
    }

    if (netboxState.state === 'error') {
      return (
        <ErrorState
          message={netboxState.error || 'Failed to load NetBox inventory'}
          onRetry={() => loadNetboxInventory(netboxPage)}
        />
      )
    }

    if (netboxState.state === 'empty') {
      return (
        <div className="card">
          <h2>Expected Network State — NetBox</h2>
          <EmptyState title="No Snapshot" message="No NetBox snapshot found. Run discovery first." />
          <div style={{ marginTop: '1rem' }}>
            <Link to="/discovery">Start Discovery →</Link>
          </div>
        </div>
      )
    }

    const inventory = netboxInventory!
    return (
      <div className="card">
        <h2>Expected Network State — NetBox</h2>
        <p className="muted">
          Canonical inventory from NetBox — captured{' '}
          {formatTimestamp(inventory.snapshot_captured_at)}
        </p>

        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            marginTop: '1rem',
          }}
        >
          <thead>
            <tr style={{ borderBottom: '2px solid #ccc' }}>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Device</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Model</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Serial</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Platform</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Management IP</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {inventory.items.map((device) => (
              <tr
                key={device.device_id}
                style={{ borderBottom: '1px solid #eee' }}
              >
                <td style={{ padding: '0.5rem' }}>{device.name || device.device_id}</td>
                <td style={{ padding: '0.5rem' }}>{device.model || '—'}</td>
                <td style={{ padding: '0.5rem' }}>{device.serial_number || '—'}</td>
                <td style={{ padding: '0.5rem' }}>{device.platform || '—'}</td>
                <td style={{ padding: '0.5rem' }}>{device.management_ip || '—'}</td>
                <td style={{ padding: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={() => handleSelectDevice(device.device_id)}
                    style={{
                      padding: '0.25rem 0.75rem',
                      fontSize: '0.875rem',
                      cursor: 'pointer',
                    }}
                  >
                    Compare
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button
            type="button"
            disabled={netboxPage <= 1}
            onClick={() => loadNetboxInventory(netboxPage - 1)}
          >
            ← Previous
          </button>
          <span style={{ fontSize: '0.875rem', color: '#666' }}>
            Page {inventory.page} of{' '}
            {Math.ceil(inventory.total / (inventory.page_size || 50))}
          </span>
          <button
            type="button"
            disabled={!inventory.has_next}
            onClick={() => loadNetboxInventory(netboxPage + 1)}
          >
            Next →
          </button>
        </div>

        <div style={{ marginTop: '1rem' }}>
          <button
            type="button"
            onClick={() => setCurrentSection('overview')}
          >
            ← Back to Overview
          </button>
        </div>
      </div>
    )
  }

  // =========================================================================
  // RENDER: Live Inventory
  // =========================================================================
  const renderLiveInventory = () => {
    if (liveState.state === 'loading') {
      return <EmptyState title="Loading" message="Loading live inventory…" />
    }

    if (liveState.state === 'error') {
      return (
        <ErrorState
          message={liveState.error || 'Failed to load live inventory'}
          onRetry={() => loadLiveInventory(livePage)}
        />
      )
    }

    if (liveState.state === 'empty') {
      return (
        <div className="card">
          <h2>Observed Network State — Live Discovery</h2>
          <EmptyState title="No Snapshot" message="No live snapshot found. Run discovery first." />
          <div style={{ marginTop: '1rem' }}>
            <Link to="/discovery">Start Discovery →</Link>
          </div>
        </div>
      )
    }

    const inventory = liveInventory!
    return (
      <div className="card">
        <h2>Observed Network State — Live Discovery</h2>
        <p className="muted">
          Real network inventory from discovery — captured{' '}
          {formatTimestamp(inventory.snapshot_captured_at)}
        </p>

        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            marginTop: '1rem',
          }}
        >
          <thead>
            <tr style={{ borderBottom: '2px solid #ccc' }}>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Device</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Model</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Serial</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Platform</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Management IP</th>
              <th style={{ textAlign: 'left', padding: '0.5rem' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {inventory.items.map((device) => (
              <tr
                key={device.device_id}
                style={{ borderBottom: '1px solid #eee' }}
              >
                <td style={{ padding: '0.5rem' }}>{device.name || device.device_id}</td>
                <td style={{ padding: '0.5rem' }}>{device.model || '—'}</td>
                <td style={{ padding: '0.5rem' }}>{device.serial_number || '—'}</td>
                <td style={{ padding: '0.5rem' }}>{device.platform || '—'}</td>
                <td style={{ padding: '0.5rem' }}>{device.management_ip || '—'}</td>
                <td style={{ padding: '0.5rem' }}>
                  <button
                    type="button"
                    onClick={() => handleSelectDevice(device.device_id)}
                    style={{
                      padding: '0.25rem 0.75rem',
                      fontSize: '0.875rem',
                      cursor: 'pointer',
                    }}
                  >
                    Compare
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button
            type="button"
            disabled={livePage <= 1}
            onClick={() => loadLiveInventory(livePage - 1)}
          >
            ← Previous
          </button>
          <span style={{ fontSize: '0.875rem', color: '#666' }}>
            Page {inventory.page} of{' '}
            {Math.ceil(inventory.total / (inventory.page_size || 50))}
          </span>
          <button
            type="button"
            disabled={!inventory.has_next}
            onClick={() => loadLiveInventory(livePage + 1)}
          >
            Next →
          </button>
        </div>

        <div style={{ marginTop: '1rem' }}>
          <button
            type="button"
            onClick={() => setCurrentSection('overview')}
          >
            ← Back to Overview
          </button>
        </div>
      </div>
    )
  }

  // =========================================================================
  // RENDER: Device Comparison
  // =========================================================================
  const renderComparison = () => {
    if (comparisonState.state === 'loading') {
      return <EmptyState title="Loading" message="Loading device comparison…" />
    }

    if (comparisonState.state === 'error') {
      return (
        <ErrorState
          message={comparisonState.error || 'Failed to load comparison'}
          onRetry={() => {
            if (selectedDeviceId) {
              void loadComparison(selectedDeviceId)
            }
          }}
        />
      )
    }

    const comp = comparison!

    return (
      <div className="card">
        <h2>Device Comparison: {comp.device_id}</h2>
        {comp.compared_at && (
          <p className="muted">Compared at {formatTimestamp(comp.compared_at)}</p>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '2rem',
            marginTop: '1.5rem',
          }}
        >
          {/* Expected State */}
          <div style={{ borderRight: '2px solid #eee', paddingRight: '1rem' }}>
            <h3>Expected State (NetBox)</h3>
            {comp.expected_state ? (
              <table
                style={{
                  width: '100%',
                  marginTop: '1rem',
                  borderCollapse: 'collapse',
                }}
              >
                <tbody>
                  {[
                    { label: 'Name', value: comp.expected_state.name },
                    { label: 'Model', value: comp.expected_state.model },
                    { label: 'Serial', value: comp.expected_state.serial_number },
                    { label: 'Platform', value: comp.expected_state.platform },
                    { label: 'Management IP', value: comp.expected_state.management_ip },
                    {
                      label: 'Manufacturer',
                      value: comp.expected_state.manufacturer,
                    },
                    {
                      label: 'Product ID',
                      value: comp.expected_state.product_id,
                    },
                  ].map(({ label, value }) => (
                    <tr
                      key={label}
                      style={{ borderBottom: '1px solid #eee' }}
                    >
                      <td
                        style={{
                          padding: '0.5rem',
                          fontWeight: 'bold',
                          width: '40%',
                        }}
                      >
                        {label}
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        {value || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p style={{ color: '#999' }}>No expected state found</p>
            )}
          </div>

          {/* Observed State */}
          <div style={{ paddingLeft: '1rem' }}>
            <h3>Observed State (Live)</h3>
            {comp.observed_state ? (
              <table
                style={{
                  width: '100%',
                  marginTop: '1rem',
                  borderCollapse: 'collapse',
                }}
              >
                <tbody>
                  {[
                    { label: 'Name', value: comp.observed_state.name },
                    { label: 'Model', value: comp.observed_state.model },
                    { label: 'Serial', value: comp.observed_state.serial_number },
                    { label: 'Platform', value: comp.observed_state.platform },
                    { label: 'Management IP', value: comp.observed_state.management_ip },
                    {
                      label: 'Manufacturer',
                      value: comp.observed_state.manufacturer,
                    },
                    {
                      label: 'Product ID',
                      value: comp.observed_state.product_id,
                    },
                  ].map(({ label, value }) => (
                    <tr
                      key={label}
                      style={{ borderBottom: '1px solid #eee' }}
                    >
                      <td
                        style={{
                          padding: '0.5rem',
                          fontWeight: 'bold',
                          width: '40%',
                        }}
                      >
                        {label}
                      </td>
                      <td style={{ padding: '0.5rem' }}>
                        {value || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p style={{ color: '#999' }}>No observed state found</p>
            )}
          </div>
        </div>

        {/* Variances */}
        {comp.variances.length > 0 && (
          <div style={{ marginTop: '2rem' }}>
            <h3>Variances ({comp.variances.length})</h3>
            <table
              style={{
                width: '100%',
                marginTop: '1rem',
                borderCollapse: 'collapse',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '2px solid #ccc' }}>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Field
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Expected
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Observed
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Type
                  </th>
                </tr>
              </thead>
              <tbody>
                {comp.variances.map((v, i) => (
                  <tr
                    key={i}
                    style={{
                      borderBottom: '1px solid #eee',
                      backgroundColor:
                        i % 2 === 0 ? '#fafafa' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>
                      {v.field_name}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {String(v.expected_value) || '—'}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {String(v.observed_value) || '—'}
                    </td>
                    <td
                      style={{
                        padding: '0.5rem',
                        fontWeight: 'bold',
                        color:
                          v.difference_type === 'MISSING'
                            ? '#d32f2f'
                            : v.difference_type === 'UNEXPECTED'
                              ? '#f57c00'
                              : v.difference_type === 'MODIFIED'
                                ? '#fbc02d'
                                : '#666',
                      }}
                    >
                      {v.difference_type}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {comp.variances.length === 0 && (
          <div
            style={{
              marginTop: '2rem',
              padding: '1rem',
              backgroundColor: '#e8f5e9',
              borderRadius: '4px',
              color: '#2e7d32',
            }}
          >
            <p>✓ No variances found. Expected and observed states match.</p>
          </div>
        )}

        {/* Drill-down buttons */}
        {(comp.expected_state || comp.observed_state) && (
          <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem' }}>
            <button
              type="button"
              onClick={() => {
                if (comp.expected_state) {
                  const snapshotId = comp.comparison_result_id || ''
                  void loadDeviceDetail(snapshotId, comp.device_id, 'interfaces')
                }
              }}
              style={{ padding: '0.5rem 1rem' }}
            >
              View Interfaces →
            </button>
            <button
              type="button"
              onClick={() => {
                if (comp.expected_state) {
                  const snapshotId = comp.comparison_result_id || ''
                  void loadDeviceDetail(snapshotId, comp.device_id, 'vlans')
                }
              }}
              style={{ padding: '0.5rem 1rem' }}
            >
              View VLANs →
            </button>
            <button
              type="button"
              onClick={() => {
                if (comp.expected_state) {
                  const snapshotId = comp.comparison_result_id || ''
                  void loadDeviceDetail(snapshotId, comp.device_id, 'neighbors')
                }
              }}
              style={{ padding: '0.5rem 1rem' }}
            >
              View Neighbors →
            </button>
          </div>
        )}

        <div style={{ marginTop: '1.5rem' }}>
          <button
            type="button"
            onClick={() => {
              setSelectedDeviceId(null)
              setComparison(null)
              setCurrentSection('overview')
            }}
          >
            ← Back to Overview
          </button>
        </div>
      </div>
    )
  }

  // =========================================================================
  // RENDER: Device Detail (Interfaces/VLANs/Neighbors)
  // =========================================================================
  const renderDetail = () => {
    if (detailState.state === 'loading') {
      return <EmptyState title="Loading" message="Loading device details…" />
    }

    if (detailState.state === 'error') {
      return (
        <ErrorState
          message={detailState.error || 'Failed to load details'}
          onRetry={() => {
            if (selectedDeviceId && detailView) {
              if (detailSnapshot) {
                void loadDeviceDetail(
                  detailSnapshot.id,
                  selectedDeviceId,
                  detailView,
                )
              }
            }
          }}
        />
      )
    }

    return (
      <div className="card">
        <h2>
          {selectedDeviceId} — {detailView ? detailView.charAt(0).toUpperCase() + detailView.slice(1) : ''}
        </h2>
        {detailSnapshot && (
          <p className="muted">
            Snapshot {detailSnapshot.id} (source: {detailSnapshot.source}) —
            captured {formatTimestamp(detailSnapshot.captured_at)}
          </p>
        )}

        {detailView === 'interfaces' && detailInterfaces && (
          <div>
            <table
              style={{
                width: '100%',
                marginTop: '1rem',
                borderCollapse: 'collapse',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '2px solid #ccc' }}>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Interface
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Description
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Status
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Speed
                  </th>
                </tr>
              </thead>
              <tbody>
                {detailInterfaces.items.map((iface) => (
                  <tr
                    key={iface.name}
                    style={{ borderBottom: '1px solid #eee' }}
                  >
                    <td style={{ padding: '0.5rem' }}>{iface.name}</td>
                    <td style={{ padding: '0.5rem' }}>
                      {iface.description || '—'}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {iface.admin_status || '—'} /{' '}
                      {iface.oper_status || '—'}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {iface.speed_mbps ? `${iface.speed_mbps} Mbps` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {detailView === 'vlans' && detailVlans && (
          <div>
            <table
              style={{
                width: '100%',
                marginTop: '1rem',
                borderCollapse: 'collapse',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '2px solid #ccc' }}>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    VLAN ID
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Name
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {detailVlans.items.map((vlan) => (
                  <tr
                    key={vlan.vlan_id}
                    style={{ borderBottom: '1px solid #eee' }}
                  >
                    <td style={{ padding: '0.5rem' }}>{vlan.vlan_id}</td>
                    <td style={{ padding: '0.5rem' }}>{vlan.name}</td>
                    <td style={{ padding: '0.5rem' }}>
                      {vlan.status || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {detailView === 'neighbors' && detailNeighbors && (
          <div>
            <table
              style={{
                width: '100%',
                marginTop: '1rem',
                borderCollapse: 'collapse',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '2px solid #ccc' }}>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Remote Device
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Local Interface
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Remote Interface
                  </th>
                  <th style={{ textAlign: 'left', padding: '0.5rem' }}>
                    Protocol
                  </th>
                </tr>
              </thead>
              <tbody>
                {detailNeighbors.items.map((neighbor, i) => (
                  <tr
                    key={i}
                    style={{ borderBottom: '1px solid #eee' }}
                  >
                    <td style={{ padding: '0.5rem' }}>
                      {neighbor.remote_device_id}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {neighbor.local_interface || '—'}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {neighbor.remote_interface || '—'}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {neighbor.protocol || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div style={{ marginTop: '1.5rem' }}>
          <button
            type="button"
            onClick={() => {
              setDetailView(null)
              setCurrentSection('comparison')
            }}
          >
            ← Back to Comparison
          </button>
        </div>
      </div>
    )
  }

  // =========================================================================
  // Main Render
  // =========================================================================
  return (
    <div className="page">
      <div className="dashboard-header">
        <div>
          <h1>Network Operations</h1>
          <p className="muted">
            Expected vs Observed Network State — NetBox vs Live Discovery
          </p>
        </div>
      </div>

      {currentSection === 'overview' && renderOverview()}
      {currentSection === 'expected' && renderExpectedInventory()}
      {currentSection === 'live' && renderLiveInventory()}
      {currentSection === 'comparison' && renderComparison()}
      {currentSection === 'detail' && renderDetail()}
    </div>
  )
}
