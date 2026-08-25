import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  cancelDiscoveryApiJob,
  discoveryJobsErrorTitle,
  listDiscoveryApiJobs,
  listDiscoveryTargets,
  resolveDiscoveryApiJobCancellation,
} from '../api/discovery'
import type {
  DiscoveryApiJobResponse,
  DiscoveryJobQueryParams,
  DiscoveryTargetResponse,
} from '../types/api'
import './JobsPage.css'

const PAGE_SIZE = 25
const activeStates = new Set(['queued', 'running'])

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : '—'
}

function truncateId(id: string) {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id
}

function hasActiveWorkerLease(job: DiscoveryApiJobResponse): boolean {
  if (job.has_active_lease !== undefined) {
    return Boolean(job.has_active_lease)
  }
  if (!job.execution_owner || !job.lease_expires_at) {
    return false
  }
  return new Date(job.lease_expires_at).getTime() > Date.now()
}

function formatDuration(
  startedAt: string | null,
  finishedAt: string | null,
  status: string,
): string {
  if (!startedAt) return '—'
  const startMs = new Date(startedAt).getTime()
  const endMs = finishedAt ? new Date(finishedAt).getTime() : Date.now()
  if (isNaN(startMs) || isNaN(endMs) || endMs < startMs) return '—'

  const diffSec = Math.floor((endMs - startMs) / 1000)
  const days = Math.floor(diffSec / 86400)
  const hours = Math.floor((diffSec % 86400) / 3600)
  const minutes = Math.floor((diffSec % 3600) / 60)
  const seconds = diffSec % 60

  let formatted = ''
  if (days > 0) {
    formatted = `${days}d ${hours}h`
  } else if (hours > 0) {
    formatted = `${hours}h ${minutes}m`
  } else if (minutes > 0) {
    formatted = `${minutes}m ${seconds}s`
  } else {
    formatted = `${seconds}s`
  }

  if (activeStates.has(status)) {
    return `Running (${formatted})`
  }
  return formatted
}

function getJobHealthBadge(job: DiscoveryApiJobResponse) {
  if (!activeStates.has(job.status)) {
    return null
  }
  if (job.started_at) {
    const runningMs = Date.now() - new Date(job.started_at).getTime()
    const runningHours = Math.floor(runningMs / (1000 * 60 * 60))
    if (runningHours >= 1) {
      return (
        <span
          className="job-warning-badge"
          title={`Execution has been active for ${runningHours} hours without completing`}
        >
          Running for {runningHours}h
        </span>
      )
    }
  }
  if (
    job.has_active_lease === false &&
    !job.last_heartbeat_at &&
    !job.execution_owner
  ) {
    return (
      <span
        className="job-warning-badge"
        title="No worker lease or heartbeat active"
      >
        Heartbeat unavailable
      </span>
    )
  }
  if (
    job.lease_expires_at &&
    new Date(job.lease_expires_at).getTime() < Date.now()
  ) {
    return (
      <span className="job-warning-badge" title="Worker lease expired">
        Lease expired
      </span>
    )
  }
  return null
}

function getDateBoundaries(
  dateFilter: string,
  customFrom?: string,
  customTo?: string,
): { date_from?: string; date_to?: string } {
  const now = new Date()
  if (dateFilter === 'today') {
    const todayStart = new Date(
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 0, 0, 0),
    )
    return { date_from: todayStart.toISOString() }
  }
  if (dateFilter === '24h') {
    const past24h = new Date(now.getTime() - 24 * 60 * 60 * 1000)
    return { date_from: past24h.toISOString() }
  }
  if (dateFilter === '7d') {
    const past7d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    return { date_from: past7d.toISOString() }
  }
  if (dateFilter === '30d') {
    const past30d = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
    return { date_from: past30d.toISOString() }
  }
  if (dateFilter === 'custom') {
    return {
      date_from: customFrom ? new Date(customFrom).toISOString() : undefined,
      date_to: customTo ? new Date(customTo).toISOString() : undefined,
    }
  }
  return {}
}

export function JobsPage() {
  const [jobs, setJobs] = useState<DiscoveryApiJobResponse[]>([])
  const [targets, setTargets] = useState<DiscoveryTargetResponse[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [hasNext, setHasNext] = useState(false)
  const [cancellingId, setCancellingId] = useState<string | null>(null)
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Filter and search state
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [targetFilter, setTargetFilter] = useState('all')
  const [dateFilter, setDateFilter] = useState('all')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [sortOption, setSortOption] = useState('newest')

  const mountedRef = useRef(false)

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchTerm)
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchTerm])

  // Load available discovery targets for target filter
  useEffect(() => {
    listDiscoveryTargets()
      .then((data) => {
        if (mountedRef.current) setTargets(data)
      })
      .catch(() => {
        // Silently ignore target list failure in filter dropdown
      })
  }, [])

  const hasActiveFilters = useMemo(() => {
    return (
      debouncedSearch.trim() !== '' ||
      statusFilter !== 'all' ||
      targetFilter !== 'all' ||
      dateFilter !== 'all' ||
      sortOption !== 'newest'
    )
  }, [debouncedSearch, statusFilter, targetFilter, dateFilter, sortOption])

  const sortParams = useMemo((): { sort?: string; order?: 'asc' | 'desc' } => {
    switch (sortOption) {
      case 'oldest':
        return { sort: 'oldest', order: 'asc' }
      case 'recently_started':
        return { sort: 'started_at', order: 'desc' }
      case 'recently_completed':
        return { sort: 'completed_at', order: 'desc' }
      case 'longest_running':
        return { sort: 'duration', order: 'desc' }
      case 'target_asc':
        return { sort: 'target', order: 'asc' }
      case 'status':
        return { sort: 'status', order: 'asc' }
      case 'newest':
      default:
        return { sort: 'requested_at', order: 'desc' }
    }
  }, [sortOption])

  const loadJobs = useCallback(
    (requestedPage: number) => {
      setStatus('loading')
      setError(null)
      const applyError = (err: unknown) => {
        if (!mountedRef.current) return
        setError(
          err instanceof Error ? err.message : 'Unable to load discovery jobs.',
        )
        setStatus('error')
      }

      const dateBounds = getDateBoundaries(dateFilter, customFrom, customTo)
      const queryParams: DiscoveryJobQueryParams = {
        page: requestedPage,
        page_size: PAGE_SIZE,
        q: debouncedSearch.trim() || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        target_id: targetFilter !== 'all' ? targetFilter : undefined,
        date_from: dateBounds.date_from,
        date_to: dateBounds.date_to,
        sort: sortParams.sort,
        order: sortParams.order,
      }

      try {
        return listDiscoveryApiJobs(queryParams).then((data) => {
          if (!mountedRef.current) return
          setJobs(data.items)
          setPage(data.page)
          setTotal(data.total)
          setTotalPages(
            data.total_pages ||
              Math.max(1, Math.ceil(data.total / (data.page_size || PAGE_SIZE))),
          )
          setHasNext(data.has_next)
          setStatus('ready')
        }, applyError)
      } catch (err) {
        applyError(err)
        return Promise.resolve()
      }
    },
    [debouncedSearch, statusFilter, targetFilter, dateFilter, customFrom, customTo, sortParams],
  )

  useEffect(() => {
    mountedRef.current = true
    void loadJobs(page)
    return () => {
      mountedRef.current = false
    }
  }, [loadJobs, page])

  const hasActiveJobs = jobs.some((job) => activeStates.has(job.status))

  useEffect(() => {
    if (!hasActiveJobs) return
    const timer = window.setInterval(() => void loadJobs(page), 2000)
    return () => window.clearInterval(timer)
  }, [hasActiveJobs, loadJobs, page])

  const handleClearFilters = () => {
    setSearchTerm('')
    setDebouncedSearch('')
    setStatusFilter('all')
    setTargetFilter('all')
    setDateFilter('all')
    setCustomFrom('')
    setCustomTo('')
    setSortOption('newest')
    setPage(1)
  }

  const cancelJob = async (job: DiscoveryApiJobResponse) => {
    const confirmed = window.confirm(
      'Stop this discovery job? In-flight network I/O may finish or time out. Already collected evidence and results will be retained.',
    )
    if (!confirmed) return
    setCancellingId(job.job_id)
    setError(null)
    try {
      await cancelDiscoveryApiJob(job.job_id)
      await loadJobs(page)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to cancel discovery job.',
      )
      setStatus('error')
    } finally {
      setCancellingId(null)
    }
  }

  const resolveCancellation = async (job: DiscoveryApiJobResponse) => {
    const confirmed = window.confirm(
      'Resolving cancellation changes the durable job state to cancelled immediately and does not terminate active network I/O or background processes. Are you sure you want to resolve cancellation for this job?',
    )
    if (!confirmed) return
    setResolvingId(job.job_id)
    setError(null)
    try {
      await resolveDiscoveryApiJobCancellation(job.job_id)
      await loadJobs(page)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to resolve discovery job cancellation.',
      )
      setStatus('error')
    } finally {
      setResolvingId(null)
    }
  }

  return (
    <div className="page jobs-page">
      <div className="dashboard-header">
        <div>
          <h2>
            Discovery Jobs
            {hasActiveJobs ? (
              <span className="jobs-live-indicator">Live</span>
            ) : null}
          </h2>
          <p className="muted">
            Monitor durable discovery executions and inspect their captured
            results.
          </p>
        </div>
        <div className="jobs-header-actions">
          <button
            type="button"
            className="btn btn-outline btn-refresh"
            onClick={() => void loadJobs(page)}
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Search, Filter, Sort Toolbar */}
      <div className="jobs-toolbar">
        <div className="jobs-search-wrap">
          <input
            type="text"
            className="jobs-search-input"
            placeholder="Search jobs..."
            aria-label="Search jobs"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          {searchTerm ? (
            <button
              type="button"
              className="jobs-search-clear"
              title="Clear search"
              onClick={() => setSearchTerm('')}
            >
              ×
            </button>
          ) : null}
        </div>

        <div className="jobs-filters-wrap">
          <div className="jobs-filter-item">
            <label htmlFor="filter-status">Status</label>
            <select
              id="filter-status"
              className="jobs-select"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
            >
              <option value="all">All</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="succeeded">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <div className="jobs-filter-item">
            <label htmlFor="filter-target">Target</label>
            <select
              id="filter-target"
              className="jobs-select"
              value={targetFilter}
              onChange={(e) => {
                setTargetFilter(e.target.value)
                setPage(1)
              }}
            >
              <option value="all">All</option>
              {targets.map((t) => (
                <option key={t.target_id} value={t.target_id}>
                  {t.identifier} ({t.address})
                </option>
              ))}
            </select>
          </div>

          <div className="jobs-filter-item">
            <label htmlFor="filter-date">Date</label>
            <select
              id="filter-date"
              className="jobs-select"
              value={dateFilter}
              onChange={(e) => {
                setDateFilter(e.target.value)
                setPage(1)
              }}
            >
              <option value="all">All time</option>
              <option value="today">Today</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          {dateFilter === 'custom' ? (
            <div className="jobs-custom-dates">
              <input
                type="datetime-local"
                className="jobs-date-input"
                aria-label="Custom date from"
                value={customFrom}
                onChange={(e) => {
                  setCustomFrom(e.target.value)
                  setPage(1)
                }}
              />
              <span>to</span>
              <input
                type="datetime-local"
                className="jobs-date-input"
                aria-label="Custom date to"
                value={customTo}
                onChange={(e) => {
                  setCustomTo(e.target.value)
                  setPage(1)
                }}
              />
            </div>
          ) : null}

          <div className="jobs-filter-item">
            <label htmlFor="filter-sort">Sort</label>
            <select
              id="filter-sort"
              className="jobs-select"
              value={sortOption}
              onChange={(e) => {
                setSortOption(e.target.value)
                setPage(1)
              }}
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="recently_started">Recently started</option>
              <option value="recently_completed">Recently completed</option>
              <option value="longest_running">Longest running</option>
              <option value="target_asc">Target A-Z</option>
              <option value="status">Status</option>
            </select>
          </div>

          {hasActiveFilters ? (
            <button
              type="button"
              className="btn btn-compact btn-clear-filters"
              onClick={handleClearFilters}
            >
              Clear filters
            </button>
          ) : null}
        </div>
      </div>

      {status === 'loading' && jobs.length === 0 ? (
        <div className="state-card">
          <p>Loading discovery jobs…</p>
        </div>
      ) : null}

      {status === 'error' ? (
        <div className="error-state" role="alert">
          <h3>{discoveryJobsErrorTitle(error)}</h3>
          <p>{error}</p>
          <button
            type="button"
            className="btn btn-outline btn-compact"
            onClick={() => void loadJobs(page)}
          >
            Retry
          </button>
        </div>
      ) : null}

      {status === 'ready' && jobs.length === 0 && !hasActiveFilters ? (
        <div className="state-card">
          <h3>No discovery jobs have been created yet.</h3>
          <p className="muted">
            Discovery executions will appear here once submitted.
          </p>
        </div>
      ) : null}

      {status === 'ready' && jobs.length === 0 && hasActiveFilters ? (
        <div className="state-card jobs-empty-search">
          <h3>No discovery jobs match the current filters.</h3>
          <p className="muted">
            Try adjusting your search keywords, status, target, or date filters.
          </p>
          <button
            type="button"
            className="btn btn-outline btn-compact"
            onClick={handleClearFilters}
          >
            Clear filters
          </button>
        </div>
      ) : null}

      {jobs.length > 0 ? (
        <div className="state-card">
          <div className="panel-heading">
            <h3>Discovery job list</h3>
            <span className="muted">
              {total} {total === 1 ? 'job' : 'jobs'} total
            </span>
          </div>
          <div className="jobs-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Target</th>
                  <th>Status</th>
                  <th>Requested</th>
                  <th>Started</th>
                  <th>Finished</th>
                  <th>Duration</th>
                  <th>Failure / Health</th>
                  <th>Details</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <div className="job-id-cell">
                        <code title={job.job_id}>{truncateId(job.job_id)}</code>
                        <button
                          type="button"
                          className="btn-copy-id"
                          title="Copy full Job ID"
                          aria-label={`Copy Job ID ${job.job_id}`}
                          onClick={() => {
                            void navigator.clipboard?.writeText(job.job_id)
                            setCopiedId(job.job_id)
                            setTimeout(() => setCopiedId(null), 1500)
                          }}
                        >
                          {copiedId === job.job_id ? '✓' : '⧉'}
                        </button>
                      </div>
                    </td>
                    <td>
                      <div className="job-target-cell">
                        <strong>
                          {job.target_identifier ||
                            job.target_address ||
                            truncateId(job.target_id)}
                        </strong>
                        {job.target_identifier && job.target_address ? (
                          <span
                            className="job-target-sub"
                            title={job.target_address}
                          >
                            {job.target_address}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      <span className={`status-pill status-${job.status}`}>
                        {job.status.replaceAll('_', ' ')}
                      </span>
                    </td>
                    <td>{formatDate(job.created_at || job.queued_at)}</td>
                    <td>{formatDate(job.started_at)}</td>
                    <td>{formatDate(job.finished_at)}</td>
                    <td>
                      <span className="job-duration-text">
                        {formatDuration(job.started_at, job.finished_at, job.status)}
                      </span>
                    </td>
                    <td className="jobs-failure-cell">
                      {getJobHealthBadge(job)}
                      {job.error_message || job.error_code ? (
                        <span
                          className="job-error-text"
                          title={job.error_message || job.error_code || undefined}
                        >
                          {job.error_message || job.error_code}
                        </span>
                      ) : null}
                      {!getJobHealthBadge(job) &&
                      !job.error_message &&
                      !job.error_code ? (
                        '—'
                      ) : null}
                    </td>
                    <td>
                      <Link to={`/discovery?job_id=${job.job_id}`}>
                        View details
                      </Link>
                    </td>
                    <td>
                      {activeStates.has(job.status) ? (
                        job.cancellation_requested_at !== null ? (
                          hasActiveWorkerLease(job) ? (
                            <button
                              type="button"
                              className="btn btn-danger btn-compact"
                              disabled
                            >
                              Cancellation requested…
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-warning btn-compact"
                              disabled={resolvingId === job.job_id}
                              onClick={() => void resolveCancellation(job)}
                            >
                              {resolvingId === job.job_id
                                ? 'Resolving…'
                                : 'Resolve cancellation'}
                            </button>
                          )
                        ) : (
                          <button
                            type="button"
                            className="btn btn-danger btn-compact"
                            disabled={cancellingId === job.job_id}
                            onClick={() => void cancelJob(job)}
                          >
                            {cancellingId === job.job_id
                              ? 'Cancelling…'
                              : 'Cancel'}
                          </button>
                        )
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="jobs-pagination">
            <button
              type="button"
              className="btn btn-outline btn-compact"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <span>
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              className="btn btn-outline btn-compact"
              disabled={!hasNext && page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

