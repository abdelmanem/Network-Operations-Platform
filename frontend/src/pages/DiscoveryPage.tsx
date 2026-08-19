import { useEffect, useState } from 'react'
import {
  createDiscoveryApiJob,
  createDiscoveryTarget,
  getDiscoveryApiJob,
  getDiscoveryEvidence,
  listDiscoveryTargets,
} from '../api/discovery'
import type {
  DiscoveryApiJobResponse,
  DiscoveryEvidenceResponse,
  DiscoveryTargetResponse,
} from '../types/api'

const terminalStates = new Set([
  'succeeded',
  'failed',
  'timed_out',
  'cancelled',
])

export function DiscoveryPage() {
  const [targets, setTargets] = useState<DiscoveryTargetResponse[]>([])
  const [selectedTargetId, setSelectedTargetId] = useState('')
  const [job, setJob] = useState<DiscoveryApiJobResponse | null>(null)
  const [evidence, setEvidence] = useState<DiscoveryEvidenceResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [savingTarget, setSavingTarget] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [targetForm, setTargetForm] = useState({
    scope_type: 'single_device' as
      'single_device' | 'ip_range' | 'cidr_network',
    identifier: '',
    address: '',
    scope_end: '',
    scope_cidr: '',
    credential_profile_id: '',
    platform_hint: 'cisco-iosxe',
    preferred_transport: 'netmiko',
  })

  async function loadTargets() {
    setLoading(true)
    setError(null)
    try {
      const data = await listDiscoveryTargets()
      setTargets(data)
      if (!selectedTargetId && data[0]) setSelectedTargetId(data[0].target_id)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to load discovery targets.',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadTargets()
  }, [])

  useEffect(() => {
    if (!job || terminalStates.has(job.status)) return
    const timer = window.setInterval(async () => {
      try {
        const updated = await getDiscoveryApiJob(job.job_id)
        setJob(updated)
        if (terminalStates.has(updated.status)) {
          setEvidence(await getDiscoveryEvidence(updated.job_id))
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Unable to poll discovery job.',
        )
      }
    }, 2000)
    return () => window.clearInterval(timer)
  }, [job])

  async function handleCreateTarget(event: React.FormEvent) {
    event.preventDefault()
    setSavingTarget(true)
    setError(null)
    try {
      const tenantId = window.localStorage.getItem('tenant-id') || 'default'
      const created = await createDiscoveryTarget({
        ...targetForm,
        address:
          targetForm.scope_type === 'cidr_network' ? null : targetForm.address,
        scope_end:
          targetForm.scope_type === 'ip_range' ? targetForm.scope_end : null,
        scope_cidr:
          targetForm.scope_type === 'cidr_network'
            ? targetForm.scope_cidr
            : null,
        tenant_id: tenantId,
        enabled: true,
        credential_references: {},
        allowed_fallback_transports: ['snmp', 'http'],
        metadata: {},
      })
      setTargets((current) => [created, ...current])
      setSelectedTargetId(created.target_id)
      setTargetForm({
        scope_type: 'single_device',
        identifier: '',
        address: '',
        scope_end: '',
        scope_cidr: '',
        credential_profile_id: '',
        platform_hint: 'cisco-iosxe',
        preferred_transport: 'netmiko',
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create target.')
    } finally {
      setSavingTarget(false)
    }
  }

  async function handleStartDiscovery() {
    if (!selectedTargetId) return
    setStarting(true)
    setError(null)
    setEvidence([])
    try {
      const created = await createDiscoveryApiJob({
        target_id: selectedTargetId,
        requested_capabilities: { collector_name: 'cisco-ios-inventory' },
        metadata: { source: 'discovery-ui' },
        timeout_seconds: 120,
        correlation_id: crypto.randomUUID(),
      })
      setJob(created)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to start discovery.',
      )
    } finally {
      setStarting(false)
    }
  }

  const selectedTarget = targets.find(
    (target) => target.target_id === selectedTargetId,
  )

  return (
    <div className="page">
      <div className="dashboard-header">
        <div>
          <h2>Network Discovery</h2>
          <p className="muted">
            Capture trusted observations from managed network targets.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadTargets()}
          disabled={loading}
        >
          Refresh targets
        </button>
      </div>

      {error ? <div className="error-state">{error}</div> : null}

      <div className="discovery-grid">
        <section className="card">
          <h3>Targets</h3>
          {loading ? <p className="muted">Loading targets…</p> : null}
          {!loading && targets.length === 0 ? (
            <p className="muted">No targets configured yet.</p>
          ) : null}
          <div className="target-list">
            {targets.map((target) => (
              <button
                className={
                  target.target_id === selectedTargetId
                    ? 'target-row selected'
                    : 'target-row'
                }
                key={target.target_id}
                type="button"
                onClick={() => setSelectedTargetId(target.target_id)}
              >
                <strong>{target.identifier}</strong>
                <span>{target.address}</span>
                <small>
                  {target.platform_hint || 'Automatic platform detection'}
                </small>
              </button>
            ))}
          </div>
        </section>

        <form className="card" onSubmit={handleCreateTarget}>
          <h3>Add target</h3>
          <fieldset>
            <legend>Discovery scope</legend>
            {[
              ['single_device', 'Single Device'],
              ['ip_range', 'IP Range'],
              ['cidr_network', 'CIDR Network'],
            ].map(([value, label]) => (
              <label key={value}>
                <input
                  type="radio"
                  name="scope_type"
                  value={value}
                  checked={targetForm.scope_type === value}
                  onChange={() =>
                    setTargetForm({
                      ...targetForm,
                      scope_type: value as typeof targetForm.scope_type,
                    })
                  }
                />
                {label}
              </label>
            ))}
          </fieldset>
          <label>
            Target name
            <input
              value={targetForm.identifier}
              required
              onChange={(event) =>
                setTargetForm({ ...targetForm, identifier: event.target.value })
              }
            />
          </label>
          {targetForm.scope_type !== 'cidr_network' ? (
            <label>
              {targetForm.scope_type === 'ip_range'
                ? 'Start IP'
                : 'Management address'}
              <input
                value={targetForm.address}
                required
                onChange={(event) =>
                  setTargetForm({ ...targetForm, address: event.target.value })
                }
              />
            </label>
          ) : null}
          {targetForm.scope_type === 'ip_range' ? (
            <label>
              End IP
              <input
                value={targetForm.scope_end}
                required
                onChange={(event) =>
                  setTargetForm({
                    ...targetForm,
                    scope_end: event.target.value,
                  })
                }
              />
            </label>
          ) : null}
          {targetForm.scope_type === 'cidr_network' ? (
            <label>
              CIDR network
              <input
                value={targetForm.scope_cidr}
                required
                placeholder="10.10.20.0/24"
                onChange={(event) =>
                  setTargetForm({
                    ...targetForm,
                    scope_cidr: event.target.value,
                  })
                }
              />
            </label>
          ) : null}
          <label>
            Credential profile ID
            <input
              value={targetForm.credential_profile_id}
              required
              placeholder="credential-profile:cisco-production"
              onChange={(event) =>
                setTargetForm({
                  ...targetForm,
                  credential_profile_id: event.target.value,
                })
              }
            />
          </label>
          <label>
            Platform
            <select
              value={targetForm.platform_hint}
              onChange={(event) =>
                setTargetForm({
                  ...targetForm,
                  platform_hint: event.target.value,
                })
              }
            >
              <option value="cisco-iosxe">Cisco IOS-XE</option>
              <option value="cisco-ios">Cisco IOS</option>
            </select>
          </label>
          <button type="submit" disabled={savingTarget}>
            {savingTarget ? 'Saving…' : 'Save target'}
          </button>
        </form>
      </div>

      <section className="card discovery-run-panel">
        <div className="panel-heading">
          <div>
            <h3>Discovery execution</h3>
            <p className="muted">
              {selectedTarget
                ? `${selectedTarget.identifier} · ${selectedTarget.address}`
                : 'Select a target to begin.'}
            </p>
          </div>
          <button
            type="button"
            disabled={
              !selectedTarget ||
              starting ||
              Boolean(job && !terminalStates.has(job.status))
            }
            onClick={() => void handleStartDiscovery()}
          >
            {starting ? 'Starting…' : 'Start discovery'}
          </button>
        </div>
        {job ? (
          <div className="run-status">
            <span className={`status-pill status-${job.status}`}>
              {job.status}
            </span>
            <span>Job {job.job_id}</span>
            {job.selected_platform ? (
              <span>Platform: {job.selected_platform}</span>
            ) : null}
            {job.selected_transport ? (
              <span>Transport: {job.selected_transport}</span>
            ) : null}
            {job.error_code ? <strong>{job.error_code}</strong> : null}
          </div>
        ) : null}
      </section>

      <section className="card">
        <h3>Discovery plan</h3>
        <div className="run-status">
          <span>
            Scope:{' '}
            <strong>{selectedTarget?.scope_type || 'Not configured'}</strong>
          </span>
          <span>
            Devices:{' '}
            <strong>{selectedTarget ? 'Configured scope' : '0'}</strong>
          </span>
          <span>Vendor: {selectedTarget?.vendor || 'Auto-detect'}</span>
          <span>
            Preferred transport:{' '}
            {selectedTarget?.preferred_transport || 'Automatic'}
          </span>
          <span>
            Credential profile:{' '}
            {selectedTarget?.credential_profile_id || 'Not configured'}
          </span>
          <span>Telnet: Disabled by default</span>
        </div>
      </section>

      {evidence.length > 0 ? (
        <section className="card">
          <h3>Evidence ({evidence.length})</h3>
          <div className="evidence-list">
            {evidence.map((record) => (
              <details key={record.evidence_id}>
                <summary>
                  {record.command_or_probe} · {record.content_hash.slice(0, 12)}
                  …
                </summary>
                <pre>{JSON.stringify(record.payload, null, 2)}</pre>
              </details>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}
