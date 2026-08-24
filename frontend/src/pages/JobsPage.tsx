import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  cancelDiscoveryApiJob,
  discoveryJobsErrorTitle,
  listDiscoveryApiJobs,
} from '../api/discovery'
import type { DiscoveryApiJobResponse } from '../types/api'

const PAGE_SIZE = 20
const activeStates = new Set(['queued', 'running'])

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : '—'
}

export function JobsPage() {
  const [jobs, setJobs] = useState<DiscoveryApiJobResponse[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [hasNext, setHasNext] = useState(false)
  const [cancellingId, setCancellingId] = useState<string | null>(null)
  const mountedRef = useRef(false)

  const loadJobs = useCallback((requestedPage: number) => {
    setStatus('loading')
    setError(null)
    const applyError = (err: unknown) => {
      if (!mountedRef.current) return
      setError(
        err instanceof Error ? err.message : 'Unable to load discovery jobs.',
      )
      setStatus('error')
    }
    try {
      return listDiscoveryApiJobs(requestedPage, PAGE_SIZE).then((data) => {
        if (!mountedRef.current) return
        setJobs(data.items)
        setPage(data.page)
        setTotal(data.total)
        setHasNext(data.has_next)
        setStatus('ready')
      }, applyError)
    } catch (err) {
      applyError(err)
      return Promise.resolve()
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    void loadJobs(1)
    return () => {
      mountedRef.current = false
    }
  }, [loadJobs])

  const hasActiveJobs = jobs.some((job) => activeStates.has(job.status))

  useEffect(() => {
    if (!hasActiveJobs) return
    const timer = window.setInterval(() => void loadJobs(page), 2000)
    return () => window.clearInterval(timer)
  }, [hasActiveJobs, loadJobs, page])

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

  return (
    <div className="page">
      <div className="dashboard-header">
        <div>
          <h2>Discovery Jobs</h2>
          <p className="muted">
            Monitor durable discovery executions and inspect their captured
            results.
          </p>
        </div>
        <button type="button" onClick={() => void loadJobs(page)}>
          Refresh
        </button>
      </div>

      {status === 'loading' ? (
        <div className="state-card">
          <p>Loading discovery jobs…</p>
        </div>
      ) : null}

      {status === 'error' ? (
        <div className="error-state" role="alert">
          <h3>{discoveryJobsErrorTitle(error)}</h3>
          <p>{error}</p>
          <button type="button" onClick={() => void loadJobs(page)}>
            Retry
          </button>
        </div>
      ) : null}

      {status === 'ready' && jobs.length === 0 ? (
        <div className="state-card">
          <h3>No discovery jobs have been created yet.</h3>
          <p className="muted">
            Discovery executions will appear here once submitted.
          </p>
        </div>
      ) : null}

      {status === 'ready' && jobs.length > 0 ? (
        <div className="state-card">
          <div className="panel-heading">
            <h3>Discovery job list</h3>
            <span className="muted">{total} total</span>
          </div>
          <div className="jobs-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Target</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Started</th>
                  <th>Finished</th>
                  <th>Failure</th>
                  <th>Details</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <code>{job.job_id}</code>
                    </td>
                    <td>
                      <code>{job.target_id}</code>
                    </td>
                    <td>
                      <span className={`status-pill status-${job.status}`}>
                        {job.status.replaceAll('_', ' ')}
                      </span>
                    </td>
                    <td>{formatDate(job.created_at)}</td>
                    <td>{formatDate(job.started_at)}</td>
                    <td>{formatDate(job.finished_at)}</td>
                    <td>{job.error_message || job.error_code || '—'}</td>
                    <td>
                      <Link to={`/discovery?job_id=${job.job_id}`}>
                        View details
                      </Link>
                    </td>
                    <td>
                      {activeStates.has(job.status) ? (
                        <button
                          type="button"
                          disabled={
                            cancellingId === job.job_id ||
                            job.cancellation_requested_at !== null
                          }
                          onClick={() => void cancelJob(job)}
                        >
                          {cancellingId === job.job_id
                            ? 'Cancelling…'
                            : job.cancellation_requested_at
                              ? 'Cancellation requested'
                              : 'Cancel'}
                        </button>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="jobs-pagination">
            <button
              type="button"
              disabled={page === 1}
              onClick={() => void loadJobs(page - 1)}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              type="button"
              disabled={!hasNext}
              onClick={() => void loadJobs(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
