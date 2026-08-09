import { useEffect, useState } from 'react'
import { cancelJob, getJobs } from '../api/jobs'
import type { JobStatusResponse } from '../types/api'

export function JobsPage() {
  const [jobs, setJobs] = useState<JobStatusResponse[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [cancellingId, setCancellingId] = useState<string | null>(null)

  const loadJobs = async () => {
    setStatus('loading')
    setError(null)
    try {
      const data = await getJobs()
      setJobs(data.items)
      setStatus('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load jobs.')
      setStatus('error')
    }
  }

  useEffect(() => {
    void loadJobs()
  }, [])

  const handleCancel = async (jobId: string) => {
    setCancellingId(jobId)
    try {
      await cancelJob(jobId)
      await loadJobs()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to cancel job.')
      setStatus('error')
    } finally {
      setCancellingId(null)
    }
  }

  return (
    <div className="page">
      <div className="dashboard-header">
        <div>
          <h2>Jobs</h2>
          <p className="muted">Inspect queued, running, and completed discovery jobs.</p>
        </div>
      </div>

      {status === 'loading' ? (
        <div className="state-card">
          <p>Loading jobs…</p>
        </div>
      ) : null}

      {status === 'error' ? (
        <div className="error-state">
          <h3>Unable to load jobs.</h3>
          <p>{error}</p>
          <button onClick={() => void loadJobs()}>Retry</button>
        </div>
      ) : null}

      {status === 'ready' && jobs.length === 0 ? (
        <div className="state-card">
          <h3>No jobs have been created yet.</h3>
          <p className="muted">Jobs created by discovery operations will appear here.</p>
        </div>
      ) : null}

      {status === 'ready' && jobs.length > 0 ? (
        <div className="state-card">
          <h3>Job list</h3>
          <table>
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id}>
                  <td>{job.job_id}</td>
                  <td>{job.status}</td>
                  <td>{job.progress != null ? `${job.progress}%` : 'n/a'}</td>
                  <td>{new Date(job.created_at).toLocaleString()}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => void handleCancel(job.job_id)}
                      disabled={cancellingId === job.job_id}
                    >
                      {cancellingId === job.job_id ? 'Cancelling…' : 'Cancel'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}
