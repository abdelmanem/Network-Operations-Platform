import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { EmptyState } from '../components/dashboard/EmptyState'
import { ErrorState } from '../components/dashboard/ErrorState'
import { KpiCard } from '../components/dashboard/KpiCard'
import { compareDevice } from '../api/devices'
import { getDiscoveryCidrVariance } from '../api/discovery'
import {
  listLiveInventory,
  listNetboxInventory,
  type InventoryQuery,
} from '../api/inventory'
import {
  getSnapshot,
  listDeviceInterfaces,
  listDeviceNeighbors,
  listDeviceVlans,
} from '../api/snapshots'
import type {
  DeviceComparisonResponse,
  InterfaceListResponse,
  InventoryListResponse,
  NeighborListResponse,
  SnapshotResponse,
  VlanListResponse,
  CidrVarianceSummaryResponse,
} from '../types/api'
import './NetworkPage.css'

type PageSection =
  'overview' | 'expected' | 'live' | 'variance' | 'comparison' | 'detail'
type DetailView = 'interfaces' | 'vlans' | 'neighbors' | null
type InventorySortKey =
  'name' | 'model' | 'serial_number' | 'platform' | 'management_ip'
type SortDirection = 'asc' | 'desc'

interface LoadState {
  state: 'loading' | 'ready' | 'empty' | 'error'
  error?: string
}

function ReportTable({
  headers,
  rows,
}: {
  headers: string[]
  rows: string[][]
}) {
  return (
    <div className="network-table-wrap">
      <table className="network-table">
        <thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={`${row[0]}-${index}`}>{row.map((value, valueIndex) => <td key={`${value}-${valueIndex}`}>{value}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

// Used only by the Variance Report so structural gaps (missing/unexpected
// devices) are computed against the FULL inventory on each side, never
// against whatever page or search/filter happens to be active on the
// Expected/Live browsing views. If a site ever exceeds this many devices
// on one side, the durable fix is a dedicated backend diff/reconciliation
// endpoint rather than pulling everything client-side — flag it if that
// ever becomes a real ceiling.
export function NetworkPage() {
  // Main state
  const [currentSection, setCurrentSection] = useState<PageSection>('overview')
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  const [detailView, setDetailView] = useState<DetailView>(null)

  // Inventory data
  const [netboxInventory, setNetboxInventory] =
    useState<InventoryListResponse | null>(null)
  const [liveInventory, setLiveInventory] =
    useState<InventoryListResponse | null>(null)
  const [netboxPage, setNetboxPage] = useState(1)
  const [livePage, setLivePage] = useState(1)
  const [netboxSearch, setNetboxSearch] = useState('')
  const [liveSearch, setLiveSearch] = useState('')
  const [netboxManufacturer, setNetboxManufacturer] = useState('')
  const [liveManufacturer, setLiveManufacturer] = useState('')
  const [netboxPlatform, setNetboxPlatform] = useState('')
  const [livePlatform, setLivePlatform] = useState('')
  const [netboxSort, setNetboxSort] = useState<{
    key: InventorySortKey
    direction: SortDirection
  }>({ key: 'name', direction: 'asc' })
  const [liveSort, setLiveSort] = useState<{
    key: InventorySortKey
    direction: SortDirection
  }>({ key: 'name', direction: 'asc' })

  const [searchParams] = useSearchParams()
  const discoveryJobId = searchParams.get('discovery_job_id')
  const discoveryRunId = searchParams.get('discovery_run_id')

  // Variance report data comes from the authoritative CIDR variance endpoint.
  const [varianceReportState, setVarianceReportState] = useState<LoadState>({
    state: 'empty',
  })
  const [varianceReport, setVarianceReport] =
    useState<CidrVarianceSummaryResponse | null>(null)
  const [varianceCategory, setVarianceCategory] = useState<
    'all' | 'netbox_only' | 'discovered_only' | 'identity_mismatch' | 'matched'
  >('all')
  const [varianceSearch, setVarianceSearch] = useState('')

  // Comparison data
  const [comparison, setComparison] = useState<DeviceComparisonResponse | null>(
    null,
  )

  // Detail data
  const [detailSnapshot, setDetailSnapshot] = useState<SnapshotResponse | null>(
    null,
  )
  const [detailInterfaces, setDetailInterfaces] =
    useState<InterfaceListResponse | null>(null)
  const [detailVlans, setDetailVlans] = useState<VlanListResponse | null>(null)
  const [detailNeighbors, setDetailNeighbors] =
    useState<NeighborListResponse | null>(null)

  // Load states
  const [netboxState, setNetboxState] = useState<LoadState>({
    state: 'loading',
  })
  const [liveState, setLiveState] = useState<LoadState>({ state: 'loading' })
  const [comparisonState, setComparisonState] = useState<LoadState>({
    state: 'loading',
  })
  const [detailState, setDetailState] = useState<LoadState>({
    state: 'loading',
  })

  // Load NetBox inventory
  const netboxQuery = useMemo<InventoryQuery>(
    () => ({
      search: netboxSearch || undefined,
      manufacturer: netboxManufacturer || undefined,
      platform: netboxPlatform || undefined,
      sort_by: netboxSort.key,
      sort_direction: netboxSort.direction,
    }),
    [netboxManufacturer, netboxPlatform, netboxSearch, netboxSort],
  )
  const liveQuery = useMemo<InventoryQuery>(
    () => ({
      search: liveSearch || undefined,
      manufacturer: liveManufacturer || undefined,
      platform: livePlatform || undefined,
      sort_by: liveSort.key,
      sort_direction: liveSort.direction,
    }),
    [liveManufacturer, livePlatform, liveSearch, liveSort],
  )

  const loadNetboxInventory = useCallback(async (page: number = 1) => {
    setNetboxState({ state: 'loading' })
    try {
      const data = await listNetboxInventory(page, 50, netboxQuery)
      setNetboxInventory(data)
      setNetboxPage(page)
      setNetboxState({ state: data.items.length === 0 ? 'empty' : 'ready' })
    } catch (err) {
      setNetboxState({
        state: 'error',
        error:
          err instanceof Error
            ? err.message
            : 'Failed to load NetBox inventory',
      })
    }
  }, [netboxQuery])

  // Load live inventory
  const loadLiveInventory = useCallback(async (page: number = 1) => {
    setLiveState({ state: 'loading' })
    try {
      const data = await listLiveInventory(page, 50, liveQuery)
      setLiveInventory(data)
      setLivePage(page)
      setLiveState({ state: data.items.length === 0 ? 'empty' : 'ready' })
    } catch (err) {
      setLiveState({
        state: 'error',
        error:
          err instanceof Error ? err.message : 'Failed to load live inventory',
      })
    }
  }, [liveQuery])

  const loadVarianceReport = useCallback(async (jobId: string) => {
    setVarianceReportState({ state: 'loading' })
    try {
      setVarianceReport(await getDiscoveryCidrVariance(jobId))
      setVarianceReportState({ state: 'ready' })
    } catch (err) {
      setVarianceReportState({
        state: 'error',
        error:
          err instanceof Error
            ? err.message
            : 'Failed to load the variance report',
      })
    }
  }, [])

  useEffect(() => {
    if (discoveryJobId) {
      setCurrentSection('variance')
      void loadVarianceReport(discoveryJobId)
    }
  }, [discoveryJobId, loadVarianceReport])

  // Load device comparison
  const loadComparison = useCallback(async (deviceId: string) => {
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
        error:
          err instanceof Error
            ? err.message
            : 'Failed to load device comparison',
      })
    }
  }, [])

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
          error:
            err instanceof Error
              ? err.message
              : 'Failed to load device details',
        })
      }
    },
    [],
  )

  // Reload from the server whenever search, filters, or sorting changes.
  // Filtering and sorting therefore apply to the complete snapshot, not just one page.
  useEffect(() => {
    const timeoutId = window.setTimeout(() => void loadNetboxInventory(1), 250)
    return () => window.clearTimeout(timeoutId)
  }, [loadNetboxInventory])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => void loadLiveInventory(1), 250)
    return () => window.clearTimeout(timeoutId)
  }, [loadLiveInventory])

  // Compute variance summary
  const varianceSummary = useMemo(() => {
    if (!netboxInventory || !liveInventory) return null

    const netboxIds = new Set(netboxInventory.items.map((d) => d.device_id))
    const liveIds = new Set(liveInventory.items.map((d) => d.device_id))

    const missing = Array.from(netboxIds).filter(
      (id) => !liveIds.has(id),
    ).length
    const unexpected = Array.from(liveIds).filter(
      (id) => !netboxIds.has(id),
    ).length
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

  const openVarianceReport = () => {
    setCurrentSection('variance')
    if (discoveryJobId) void loadVarianceReport(discoveryJobId)
  }

  // Format timestamp for display
  const formatTimestamp = (ts: string | null | undefined) => {
    if (!ts) return 'Unknown'
    try {
      return new Date(ts).toLocaleString()
    } catch {
      return ts
    }
  }

  // Map a variance's difference_type to a diff-badge class, same fallback
  // ladder as the original inline color ternary.
  const varianceBadgeClass = (differenceType: string) => {
    const key =
      differenceType === 'MISSING'
        ? 'missing'
        : differenceType === 'UNEXPECTED'
          ? 'unexpected'
          : differenceType === 'MODIFIED'
            ? 'modified'
            : 'default'
    return `network-diff-badge network-diff-badge-${key}`
  }

  const renderInventoryControls = (
    inventory: InventoryListResponse,
    search: string,
    setSearch: (value: string) => void,
    manufacturer: string,
    setManufacturer: (value: string) => void,
    platform: string,
    setPlatform: (value: string) => void,
  ) => {
    const manufacturers = inventory.manufacturers || []
    const platforms = inventory.platforms || []

    return (
      <div className="network-table-controls">
        <label className="network-search-label">
          <span className="sr-only">Search all device values</span>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search all values…"
            aria-label="Search all device values"
          />
        </label>
        <label>
          <span>Manufacturer</span>
          <select
            value={manufacturer}
            onChange={(event) => setManufacturer(event.target.value)}
          >
            <option value="">All manufacturers</option>
            {manufacturers.map((value) => (
              <option key={value} value={value!}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Platform</span>
          <select
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
          >
            <option value="">All platforms</option>
            {platforms.map((value) => (
              <option key={value} value={value!}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
    )
  }

  const renderSortableHeader = (
    label: string,
    key: InventorySortKey,
    sort: { key: InventorySortKey; direction: SortDirection },
    setSort: (value: {
      key: InventorySortKey
      direction: SortDirection
    }) => void,
  ) => {
    const isActive = sort.key === key
    const nextDirection: SortDirection =
      isActive && sort.direction === 'asc' ? 'desc' : 'asc'
    return (
      <th
        aria-sort={
          isActive
            ? sort.direction === 'asc'
              ? 'ascending'
              : 'descending'
            : 'none'
        }
      >
        <button
          type="button"
          className="network-sort-button"
          onClick={() => setSort({ key, direction: nextDirection })}
        >
          {label}{' '}
          <span aria-hidden="true">
            {isActive ? (sort.direction === 'asc' ? '↑' : '↓') : '↕'}
          </span>
        </button>
      </th>
    )
  }

  // RENDER: Overview Section
  // =========================================================================
  const renderOverview = () => (
    <div className="card">
      <h2>Network Operations Overview</h2>
      <p className="muted">
        Expected state (NetBox) vs Observed state (Live Discovery)
      </p>

      <div className="network-kpi-grid">
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
        <div className="network-meta-line">
          <p>
            <strong>Expected State:</strong>{' '}
            {formatTimestamp(netboxInventory.snapshot_captured_at)} (Source:{' '}
            {netboxInventory.source})
          </p>
        </div>
      )}

      {liveInventory && (
        <div className="network-meta-line">
          <p>
            <strong>Observed State:</strong>{' '}
            {formatTimestamp(liveInventory.snapshot_captured_at)} (Source:{' '}
            {liveInventory.source})
          </p>
        </div>
      )}

      <div className="network-actions">
        <button
          type="button"
          className="btn btn-primary"
          onClick={openVarianceReport}
        >
          View Variance Report →
        </button>
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => setCurrentSection('expected')}
        >
          View Expected Inventory →
        </button>
        <button
          type="button"
          className="btn btn-outline"
          onClick={() => setCurrentSection('live')}
        >
          View Live Inventory →
        </button>
      </div>

      <div className="network-callout">
        <h3>Discovery & Jobs</h3>
        <p className="muted">
          Manage network discovery runs and view job status.
        </p>
        <Link to="/discovery" className="network-link">
          View Discovery →
        </Link>
        <Link to="/jobs" className="network-link">
          View Jobs →
        </Link>
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
          <EmptyState
            title="No Snapshot"
            message="No NetBox snapshot found. Run discovery first."
          />
          <div className="network-back">
            <Link to="/discovery" className="network-link">
              Start Discovery →
            </Link>
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

        {renderInventoryControls(
          inventory,
          netboxSearch,
          setNetboxSearch,
          netboxManufacturer,
          setNetboxManufacturer,
          netboxPlatform,
          setNetboxPlatform,
        )}
        <p className="network-result-count">
          Showing {inventory.items.length} of {inventory.total} matching devices
        </p>

        <div className="network-table-wrap">
          <table className="network-table">
            <thead>
              <tr>
                {renderSortableHeader(
                  'Device',
                  'name',
                  netboxSort,
                  setNetboxSort,
                )}
                {renderSortableHeader(
                  'Model',
                  'model',
                  netboxSort,
                  setNetboxSort,
                )}
                {renderSortableHeader(
                  'Serial',
                  'serial_number',
                  netboxSort,
                  setNetboxSort,
                )}
                {renderSortableHeader(
                  'Platform',
                  'platform',
                  netboxSort,
                  setNetboxSort,
                )}
                {renderSortableHeader(
                  'Management IP',
                  'management_ip',
                  netboxSort,
                  setNetboxSort,
                )}
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {inventory.items.map((device) => (
                <tr key={device.device_id}>
                  <td>{device.name || device.device_id}</td>
                  <td>{device.model || '—'}</td>
                  <td>{device.serial_number || '—'}</td>
                  <td>{device.platform || '—'}</td>
                  <td>{device.management_ip || '—'}</td>
                  <td>
                    <button
                      type="button"
                      className="network-table-action-btn"
                      onClick={() => handleSelectDevice(device.device_id)}
                    >
                      Compare
                    </button>
                  </td>
                </tr>
              ))}
              {inventory.items.length === 0 && (
                <tr>
                  <td colSpan={6} className="network-no-results">
                    No devices match the current search and filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="network-pagination">
          <button
            type="button"
            className="btn btn-outline btn-compact"
            disabled={netboxPage <= 1}
            onClick={() => loadNetboxInventory(netboxPage - 1)}
          >
            ← Previous
          </button>
          <span className="network-page-indicator">
            Page {inventory.page} of{' '}
            {Math.ceil(inventory.total / (inventory.page_size || 50))}
          </span>
          <button
            type="button"
            className="btn btn-outline btn-compact"
            disabled={!inventory.has_next}
            onClick={() => loadNetboxInventory(netboxPage + 1)}
          >
            Next →
          </button>
        </div>

        <div className="network-back">
          <button
            type="button"
            className="btn btn-ghost"
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
          <EmptyState
            title="No Snapshot"
            message="No live snapshot found. Run discovery first."
          />
          <div className="network-back">
            <Link to="/discovery" className="network-link">
              Start Discovery →
            </Link>
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

        {renderInventoryControls(
          inventory,
          liveSearch,
          setLiveSearch,
          liveManufacturer,
          setLiveManufacturer,
          livePlatform,
          setLivePlatform,
        )}
        <p className="network-result-count">
          Showing {inventory.items.length} of {inventory.total} matching devices
        </p>

        <div className="network-table-wrap">
          <table className="network-table">
            <thead>
              <tr>
                {renderSortableHeader('Device', 'name', liveSort, setLiveSort)}
                {renderSortableHeader('Model', 'model', liveSort, setLiveSort)}
                {renderSortableHeader(
                  'Serial',
                  'serial_number',
                  liveSort,
                  setLiveSort,
                )}
                {renderSortableHeader(
                  'Platform',
                  'platform',
                  liveSort,
                  setLiveSort,
                )}
                {renderSortableHeader(
                  'Management IP',
                  'management_ip',
                  liveSort,
                  setLiveSort,
                )}
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {inventory.items.map((device) => (
                <tr key={device.device_id}>
                  <td>{device.name || device.device_id}</td>
                  <td>{device.model || '—'}</td>
                  <td>{device.serial_number || '—'}</td>
                  <td>{device.platform || '—'}</td>
                  <td>{device.management_ip || '—'}</td>
                  <td>
                    <button
                      type="button"
                      className="network-table-action-btn"
                      onClick={() => handleSelectDevice(device.device_id)}
                    >
                      Compare
                    </button>
                  </td>
                </tr>
              ))}
              {inventory.items.length === 0 && (
                <tr>
                  <td colSpan={6} className="network-no-results">
                    No devices match the current search and filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="network-pagination">
          <button
            type="button"
            className="btn btn-outline btn-compact"
            disabled={livePage <= 1}
            onClick={() => loadLiveInventory(livePage - 1)}
          >
            ← Previous
          </button>
          <span className="network-page-indicator">
            Page {inventory.page} of{' '}
            {Math.ceil(inventory.total / (inventory.page_size || 50))}
          </span>
          <button
            type="button"
            className="btn btn-outline btn-compact"
            disabled={!inventory.has_next}
            onClick={() => loadLiveInventory(livePage + 1)}
          >
            Next →
          </button>
        </div>

        <div className="network-back">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setCurrentSection('overview')}
          >
            ← Back to Overview
          </button>
        </div>
      </div>
    )
  }

  // =========================================================================
  // RENDER: Variance Report — the direct answer to "where do NetBox and the
  // real network disagree", computed from the complete inventories on both
  // sides rather than whatever page/search/filter is active elsewhere.
  // =========================================================================
  const renderVarianceReport = () => {
    if (!discoveryJobId) {
      return (
        <div className="card">
          <h2>Network Variance Report</h2>
          <p className="muted">Open this report from a completed CIDR discovery job.</p>
          <Link to="/discovery" className="network-link">Back to Discovery</Link>
        </div>
      )
    }
    if (varianceReportState.state === 'loading' || !varianceReport) {
      return (
        <EmptyState
          title="Loading"
          message="Comparing the complete NetBox and live inventories…"
        />
      )
    }

    if (varianceReportState.state === 'error') {
      return (
        <ErrorState
          message={
            varianceReportState.error || 'Failed to load the variance report'
          }
          onRetry={() => {
            if (discoveryJobId) void loadVarianceReport(discoveryJobId)
          }}
        />
      )
    }

    const { summary, variances } = varianceReport
    const categoryItems = varianceCategory === 'all'
      ? [...variances.netbox_only, ...variances.discovered_only, ...variances.identity_mismatch]
      : varianceCategory === 'netbox_only'
        ? variances.netbox_only
      : varianceCategory === 'discovered_only'
        ? variances.discovered_only
        : varianceCategory === 'identity_mismatch'
          ? variances.identity_mismatch
          : []
    const filteredItems = categoryItems.filter((item) =>
      [item.address, item.name, item.expected_name, item.observed_name, item.serial, item.model]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(varianceSearch.toLowerCase())),
    )

    return (
      <div className="card">
        <h2>Network Variance Report</h2>
        <p className="muted">
          Target: {varianceReport.target_identifier || '—'} · CIDR: {varianceReport.cidr || '—'} · Job: {varianceReport.discovery_job_id || discoveryJobId} · Run: {discoveryRunId || '—'}
        </p>
        <p className="muted">
          Status: {varianceReport.discovery_status || '—'} · Run: {formatTimestamp(varianceReport.discovery_run_started_at)} · NetBox snapshot: {formatTimestamp(varianceReport.netbox_snapshot_timestamp)} · Vendor: {varianceReport.vendor || '—'} · Platform: {varianceReport.platform || '—'}
        </p>
        <p className="network-variance-note">
          Confirmed Variances are inventory differences. Unverified addresses were not network-tested and are not considered missing devices.
        </p>

        <div className="network-variance-summary">
          <div className="network-variance-summary-item network-variance-summary-missing">
            <span>Discovered</span>
            <strong>{summary.discovered}</strong>
          </div>
          <div className="network-variance-summary-item network-variance-summary-unexpected">
            <span>NetBox</span>
            <strong>{summary.netbox}</strong>
          </div>
          <div className="network-variance-summary-item network-variance-summary-matched">
            <span>Matched</span>
            <strong>{summary.matched}</strong>
          </div>
          <div className="network-variance-summary-item network-variance-summary-missing">
            <span>Confirmed Variances</span>
            <strong>{summary.variances}</strong>
          </div>
        </div>

        <div className="network-variance-report-section">
          <div className="network-table-controls">
            <input type="search" aria-label="Search variance records" placeholder="Search IP, name, or serial" value={varianceSearch} onChange={(event) => setVarianceSearch(event.target.value)} />
          </div>
          <div className="network-actions">
            {(['all', 'netbox_only', 'discovered_only', 'identity_mismatch', 'matched'] as const).map((category) => (
              <button type="button" key={category} className="btn btn-outline" onClick={() => setVarianceCategory(category)}>{category === 'all' ? 'All Variances' : category === 'netbox_only' ? 'NetBox Only' : category === 'discovered_only' ? 'Discovered Only' : category === 'identity_mismatch' ? 'Identity Mismatch' : 'Matched'}</button>
            ))}
          </div>
          {varianceCategory === 'matched' ? (
            <ReportTable headers={['Address', 'Discovered', 'NetBox', 'Match method', 'Model', 'Serial', 'Status']} rows={variances.matched.filter((item) => [item.address, item.discovered_name, item.netbox_name, item.serial].filter(Boolean).some((value) => value!.toLowerCase().includes(varianceSearch.toLowerCase()))).map((item) => [item.address, item.discovered_name || '—', item.netbox_name || '—', item.identity_match_method || '—', item.model || '—', item.serial || '—', item.status || item.state || '—'])} />
          ) : filteredItems.length === 0 ? (
            <p className="network-diff-empty">No records in this category.</p>
          ) : (
            <ReportTable headers={['Address', 'NetBox Name', 'Serial', 'Model', 'Role', 'Status']} rows={filteredItems.map((item) => [item.address, item.name || item.expected_name || item.observed_name || '—', item.serial || '—', item.model || '—', item.role || '—', item.status || '—'])} />
          )}
        </div>

        <div className="network-variance-report-section">
          <h3>Operational results</h3>
          <p>Unverified: {summary.unverified}. Unverified ≠ Missing. These addresses were not network-tested because management transport was unavailable.</p>
          <ReportTable headers={['Unverified address', 'Reason']} rows={variances.unverified.map((item) => [item.address, item.reason || 'Management transport unavailable'])} />
          <p>Unreachable: {varianceReport.unreachable}. An actual connection failure was observed.</p>
          <ReportTable headers={['Unreachable address', 'State', 'Failure', 'Reason']} rows={variances.unreachable.map((item) => [item.address, item.state || '—', item.failure_code || '—', item.reason || '—'])} />
        </div>

        <div className="network-back">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setCurrentSection('overview')}
          >
            ← Back to Overview
          </button>
        </div>
        <Link to="/discovery" className="network-link">Back to Discovery</Link>
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
          <p className="muted">
            Compared at {formatTimestamp(comp.compared_at)}
          </p>
        )}

        <div className="network-diff">
          {/* Expected State */}
          <div className="network-diff-panel network-diff-expected">
            <h3>Expected State (NetBox)</h3>
            {comp.expected_state ? (
              <table className="network-diff-table">
                <tbody>
                  {[
                    { label: 'Name', value: comp.expected_state.name },
                    { label: 'Model', value: comp.expected_state.model },
                    {
                      label: 'Serial',
                      value: comp.expected_state.serial_number,
                    },
                    { label: 'Platform', value: comp.expected_state.platform },
                    {
                      label: 'Management IP',
                      value: comp.expected_state.management_ip,
                    },
                    {
                      label: 'Manufacturer',
                      value: comp.expected_state.manufacturer,
                    },
                    {
                      label: 'Product ID',
                      value: comp.expected_state.product_id,
                    },
                  ].map(({ label, value }) => (
                    <tr key={label}>
                      <td>{label}</td>
                      <td>{value || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="network-diff-empty">No expected state found</p>
            )}
          </div>

          {/* Observed State */}
          <div className="network-diff-panel network-diff-observed">
            <h3>Observed State (Live)</h3>
            {comp.observed_state ? (
              <table className="network-diff-table">
                <tbody>
                  {[
                    { label: 'Name', value: comp.observed_state.name },
                    { label: 'Model', value: comp.observed_state.model },
                    {
                      label: 'Serial',
                      value: comp.observed_state.serial_number,
                    },
                    { label: 'Platform', value: comp.observed_state.platform },
                    {
                      label: 'Management IP',
                      value: comp.observed_state.management_ip,
                    },
                    {
                      label: 'Manufacturer',
                      value: comp.observed_state.manufacturer,
                    },
                    {
                      label: 'Product ID',
                      value: comp.observed_state.product_id,
                    },
                  ].map(({ label, value }) => (
                    <tr key={label}>
                      <td>{label}</td>
                      <td>{value || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="network-diff-empty">No observed state found</p>
            )}
          </div>
        </div>

        {/* Variances */}
        {comp.variances.length > 0 && (
          <div className="network-variance-section">
            <h3>Variances ({comp.variances.length})</h3>
            <table className="network-variance-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Expected</th>
                  <th>Observed</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {comp.variances.map((v, i) => (
                  <tr key={i}>
                    <td className="network-variance-field">{v.field_name}</td>
                    <td>{String(v.expected_value) || '—'}</td>
                    <td>{String(v.observed_value) || '—'}</td>
                    <td>
                      <span className={varianceBadgeClass(v.difference_type)}>
                        {v.difference_type}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {comp.variances.length === 0 && (
          <div className="network-success-banner">
            <p>✓ No variances found. Expected and observed states match.</p>
          </div>
        )}

        {/* Drill-down buttons */}
        {(comp.expected_state || comp.observed_state) && (
          <div className="network-actions">
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => {
                if (comp.expected_state) {
                  const snapshotId = comp.comparison_result_id || ''
                  void loadDeviceDetail(
                    snapshotId,
                    comp.device_id,
                    'interfaces',
                  )
                }
              }}
            >
              View Interfaces →
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => {
                if (comp.expected_state) {
                  const snapshotId = comp.comparison_result_id || ''
                  void loadDeviceDetail(snapshotId, comp.device_id, 'vlans')
                }
              }}
            >
              View VLANs →
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={() => {
                if (comp.expected_state) {
                  const snapshotId = comp.comparison_result_id || ''
                  void loadDeviceDetail(snapshotId, comp.device_id, 'neighbors')
                }
              }}
            >
              View Neighbors →
            </button>
          </div>
        )}

        <div className="network-back network-back-lg">
          <button
            type="button"
            className="btn btn-ghost"
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
          {selectedDeviceId} —{' '}
          {detailView
            ? detailView.charAt(0).toUpperCase() + detailView.slice(1)
            : ''}
        </h2>
        {detailSnapshot && (
          <p className="muted">
            Snapshot {detailSnapshot.id} (source: {detailSnapshot.source}) —
            captured {formatTimestamp(detailSnapshot.captured_at)}
          </p>
        )}

        {detailView === 'interfaces' && detailInterfaces && (
          <div className="network-table-wrap">
            <table className="network-table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Description</th>
                  <th>Status</th>
                  <th>Speed</th>
                </tr>
              </thead>
              <tbody>
                {detailInterfaces.items.map((iface) => (
                  <tr key={iface.name}>
                    <td>{iface.name}</td>
                    <td>{iface.description || '—'}</td>
                    <td>
                      {iface.admin_status || '—'} / {iface.oper_status || '—'}
                    </td>
                    <td>
                      {iface.speed_mbps ? `${iface.speed_mbps} Mbps` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {detailView === 'vlans' && detailVlans && (
          <div className="network-table-wrap">
            <table className="network-table">
              <thead>
                <tr>
                  <th>VLAN ID</th>
                  <th>Name</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {detailVlans.items.map((vlan) => (
                  <tr key={vlan.vlan_id}>
                    <td>{vlan.vlan_id}</td>
                    <td>{vlan.name}</td>
                    <td>{vlan.status || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {detailView === 'neighbors' && detailNeighbors && (
          <div className="network-table-wrap">
            <table className="network-table">
              <thead>
                <tr>
                  <th>Remote Device</th>
                  <th>Local Interface</th>
                  <th>Remote Interface</th>
                  <th>Protocol</th>
                </tr>
              </thead>
              <tbody>
                {detailNeighbors.items.map((neighbor, i) => (
                  <tr key={i}>
                    <td>{neighbor.remote_device_id}</td>
                    <td>{neighbor.local_interface || '—'}</td>
                    <td>{neighbor.remote_interface || '—'}</td>
                    <td>{neighbor.protocol || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="network-back">
          <button
            type="button"
            className="btn btn-ghost"
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
    <div className="page network-page">
      <div className="dashboard-header network-page-header">
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
      {currentSection === 'variance' && renderVarianceReport()}
      {currentSection === 'comparison' && renderComparison()}
      {currentSection === 'detail' && renderDetail()}
    </div>
  )
}
