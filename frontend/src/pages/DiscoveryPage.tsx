import { useEffect, useState } from 'react'
import { getDiscoveryRuns, submitDiscoveryJob } from '../api/discovery'
import type { DiscoveryJobRequest, DiscoveryRunSummaryResponse } from '../types/api'

const emptyForm: DiscoveryJobRequest = {
  collector_contexts: [{ target: { identifier: '', address: '', metadata: {} } }],
  policies: [],
  metadata: {},
  priority: 0,
  timeout_seconds: null,
}

export function DiscoveryPage() {
  const [runs, setRuns] = useState<DiscoveryRunSummaryResponse[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<DiscoveryJobRequest>(emptyForm)
  const [submitting, setSubmitting] = useState(false)
  const [submittedMessage, setSubmittedMessage] = useState<string | null>(null)

  const loadRuns = async () => {
    setStatus('loading')
    setError(null)
    try {
      const data = await getDiscoveryRuns()
      setRuns(data.items)
      setStatus('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load discovery runs.')
      setStatus('error')
    }
  }

  useEffect(() => {
    void loadRuns()
  }, [])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (submitting) return

    setSubmitting(true)
    setSubmittedMessage(null)
    try {
      const payload: DiscoveryJobRequest = {
        collector_contexts: [
          {
            target: {
              identifier: form.collector_contexts[0]?.target.identifier ?? '',
              address: form.collector_contexts[0]?.target.address ?? '',
              metadata: form.collector_contexts[0]?.target.metadata ?? {},
            },
          },
        ],
        policies: form.policies,
        metadata: form.metadata,
        priority: form.priority,
        timeout_seconds: form.timeout_seconds,
      }
      await submitDiscoveryJob(payload)
      setSubmittedMessage('Discovery submitted.')
      await loadRuns()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to submit discovery.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <div className="dashboard-header">
        <div>
          <h2>Discovery</h2>
          <p className="muted">Create and inspect discovery jobs from the live backend.</p>
        </div>
      </div>

      <form className="card" onSubmit={handleSubmit}>
        <h3>Create discovery</h3>
        <label>
          Target identifier
          <input
            aria-label="Target identifier"
            value={form.collector_contexts[0]?.target.identifier ?? ''}
            onChange={(event) => {
              const next = { ...form }
              next.collector_contexts = [
                {
                  target: {
                    ...next.collector_contexts[0]?.target,
                    identifier: event.target.value,
                  },
                },
              ]
              setForm(next)
            }}
          />
        </label>
        <label>
          Target address
          <input
            aria-label="Target address"
            value={form.collector_contexts[0]?.target.address ?? ''}
            onChange={(event) => {
              const next = { ...form }
              next.collector_contexts = [
                {
                  target: {
                    ...next.collector_contexts[0]?.target,
                    address: event.target.value,
                  },
                },
              ]
              setForm(next)
            }}
          />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting…' : 'Run discovery'}
        </button>
      </form>

      {submittedMessage ? <p className="muted">{submittedMessage}</p> : null}

      {status === 'loading' ? (
        <div className="state-card">
          <p>Loading discovery runs…</p>
        </div>
      ) : null}

      {status === 'error' ? (
        <div className="error-state">
          <h3>Unable to load discovery runs.</h3>
          <p>{error}</p>
          <button onClick={() => void loadRuns()}>Retry</button>
        </div>
      ) : null}

      {status === 'ready' && runs.length === 0 ? (
        <div className="state-card">
          <h3>No discovery runs have been created yet.</h3>
          <p className="muted">Discovery submissions will appear here after the backend records them.</p>
        </div>
      ) : null}

      {status === 'ready' && runs.length > 0 ? (
        <div className="state-card">
          <h3>Discovery runs</h3>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Target</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.id}</td>
                  <td>{run.target_identifier}</td>
                  <td>{run.status}</td>
                  <td>{new Date(run.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}
