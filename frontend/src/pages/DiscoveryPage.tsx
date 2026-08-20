import { useEffect, useState } from 'react'
import {
  createDiscoveryApiJob,
  createDiscoveryCredentialProfile,
  createDiscoveryTarget,
  getDiscoveryApiJob,
  getDiscoveryEvidence,
  getDiscoveryDeviceResults,
  listDiscoveryCredentialProfiles,
  listDiscoveryTargets,
} from '../api/discovery'
import type {
  CredentialProfileResponse,
  DiscoveryApiJobResponse,
  DiscoveryEvidenceResponse,
  DiscoveryDeviceResultResponse,
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
  const [profiles, setProfiles] = useState<CredentialProfileResponse[]>([])
  const [selectedTargetId, setSelectedTargetId] = useState('')
  const [job, setJob] = useState<DiscoveryApiJobResponse | null>(null)
  const [evidence, setEvidence] = useState<DiscoveryEvidenceResponse[]>([])
  const [deviceResults, setDeviceResults] = useState<
    DiscoveryDeviceResultResponse[]
  >([])
  const [loading, setLoading] = useState(true)
  const [savingTarget, setSavingTarget] = useState(false)
  const [creatingProfile, setCreatingProfile] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showProfileComposer, setShowProfileComposer] = useState(false)
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
  const [profileForm, setProfileForm] = useState({
    name: '',
    description: '',
    vendor: 'cisco',
    platform: 'cisco-iosxe',
    credential_type: 'ssh_password',
    username: '',
    transport_types: ['ssh'],
    provider_reference: '',
  })

  const credentialTypeHelp: Record<
    string,
    { label: string; summary: string; transport_types: string[] }
  > = {
    ssh_password: {
      label: 'SSH password',
      summary:
        'Use a username and password for an SSH transport. The secret is resolved at execution time and is not stored in the discovery target.',
      transport_types: ['ssh'],
    },
    ssh_key: {
      label: 'SSH key',
      summary:
        'Use an SSH key-based profile. The secret is resolved from the configured provider reference at runtime.',
      transport_types: ['ssh'],
    },
    snmp_v2c: {
      label: 'SNMPv2c community',
      summary:
        'Use a community string for SNMPv2c. This profile should only be used for SNMP-based discovery.',
      transport_types: ['snmp'],
    },
    snmp_v3: {
      label: 'SNMPv3',
      summary:
        'Use SNMPv3 authentication material for SNMP discovery. The profile is scoped to the SNMP transport.',
      transport_types: ['snmp'],
    },
  }

  const activeCredentialType =
    credentialTypeHelp[profileForm.credential_type] ??
    credentialTypeHelp.ssh_password

  const profileRequiresUsername =
    profileForm.credential_type === 'ssh_password' ||
    profileForm.credential_type === 'ssh_key' ||
    profileForm.credential_type === 'snmp_v3'

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

  async function loadProfiles() {
    try {
      const data = await listDiscoveryCredentialProfiles()
      setProfiles(data)
      if (!targetForm.credential_profile_id && data[0]) {
        setTargetForm((current) => ({
          ...current,
          credential_profile_id: data[0].profile_id,
        }))
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to load credential profiles.',
      )
    }
  }

  useEffect(() => {
    void Promise.all([loadTargets(), loadProfiles()])
  }, [])

  useEffect(() => {
    if (!job || terminalStates.has(job.status)) return
    const timer = window.setInterval(async () => {
      try {
        const updated = await getDiscoveryApiJob(job.job_id)
        setJob(updated)
        setDeviceResults(await getDiscoveryDeviceResults(updated.job_id))
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
      const credentialProfileId =
        targetForm.credential_profile_id || profiles[0]?.profile_id || ''
      if (!credentialProfileId) {
        throw new Error('A credential profile is required before creating a target.')
      }
      const created = await createDiscoveryTarget({
        ...targetForm,
        credential_profile_id: credentialProfileId,
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

  async function handleCreateProfile(event: React.FormEvent) {
    event.preventDefault()
    setCreatingProfile(true)
    setError(null)
    try {
      const payload = {
        name: profileForm.name.trim(),
        description: profileForm.description.trim() || null,
        vendor: profileForm.vendor || null,
        platform: profileForm.platform || null,
        credential_type: profileForm.credential_type || null,
        username: profileForm.username.trim() || null,
        transport_types: profileForm.transport_types,
        provider_reference: profileForm.provider_reference.trim(),
      }
      if (!payload.name || !payload.provider_reference) {
        throw new Error('Profile name and provider reference are required.')
      }
      if (profileRequiresUsername && !payload.username) {
        throw new Error('Username is required for the selected credential type.')
      }
      const created = await createDiscoveryCredentialProfile(payload)
      const refreshed = await listDiscoveryCredentialProfiles()
      setProfiles(refreshed)
      setTargetForm((current) => ({
        ...current,
        credential_profile_id: created.profile_id,
      }))
      setProfileForm({
        name: '',
        description: '',
        vendor: 'cisco',
        platform: 'cisco-iosxe',
        credential_type: 'ssh_password',
        username: '',
        transport_types: ['ssh'],
        provider_reference: '',
      })
      setShowProfileComposer(false)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to create credential profile.',
      )
    } finally {
      setCreatingProfile(false)
    }
  }

  async function handleStartDiscovery() {
    if (!selectedTargetId) return
    setStarting(true)
    setError(null)
    setEvidence([])
    setDeviceResults([])
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
          {profiles.length === 0 && !showProfileComposer ? (
            <div className="empty-state">
              <p>
                No credential profiles are configured. A credential profile is
                required to discover network devices.
              </p>
              <button
                type="button"
                onClick={() => setShowProfileComposer(true)}
              >
                + Create Credential Profile
              </button>
            </div>
          ) : null}

          {!showProfileComposer && profiles.length > 0 ? (
            <label>
              Credential profile
              <select
                value={targetForm.credential_profile_id || profiles[0]?.profile_id || ''}
                required
                onChange={(event) =>
                  setTargetForm({
                    ...targetForm,
                    credential_profile_id: event.target.value,
                  })
                }
              >
                <option value="">Select a credential profile</option>
                {profiles.map((profile) => (
                  <option key={profile.profile_id} value={profile.profile_id}>
                    {profile.name} ({profile.transport_types.join(', ')})
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {!showProfileComposer && profiles.length > 0 ? (
            <button
              type="button"
              className="secondary"
              onClick={() => setShowProfileComposer(true)}
            >
              + Create Credential Profile
            </button>
          ) : null}

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
          <button type="submit" disabled={savingTarget || (!showProfileComposer && profiles.length === 0)}>
            {savingTarget ? 'Saving…' : 'Save target'}
          </button>
        </form>
      </div>

      {showProfileComposer ? (
        <div className="card">
          <form className="credential-profile-form" onSubmit={handleCreateProfile}>
            <h4>Create credential profile</h4>
            <p className="muted">
              This profile references a securely managed secret provider. The
              actual secret is resolved at execution time and is not stored in the
              discovery target.
            </p>
            <label>
              Profile name *
              <input
                value={profileForm.name}
                required
                onChange={(event) =>
                  setProfileForm({ ...profileForm, name: event.target.value })
                }
              />
            </label>
            <label>
              Description
              <input
                value={profileForm.description}
                onChange={(event) =>
                  setProfileForm({
                    ...profileForm,
                    description: event.target.value,
                  })
                }
              />
            </label>
            <label>
              Vendor *
              <input
                value={profileForm.vendor}
                required
                onChange={(event) =>
                  setProfileForm({ ...profileForm, vendor: event.target.value })
                }
              />
            </label>
            <label>
              Platform *
              <input
                value={profileForm.platform}
                required
                onChange={(event) =>
                  setProfileForm({ ...profileForm, platform: event.target.value })
                }
              />
            </label>
            <label>
              Credential type *
              <select
                value={profileForm.credential_type}
                onChange={(event) => {
                  const nextType = event.target.value
                  setProfileForm({
                    ...profileForm,
                    credential_type: nextType,
                    transport_types: credentialTypeHelp[nextType]?.transport_types ?? ['ssh'],
                  })
                }}
              >
                <option value="ssh_password">SSH password</option>
                <option value="ssh_key">SSH key</option>
                <option value="snmp_v2c">SNMPv2c community</option>
                <option value="snmp_v3">SNMPv3</option>
              </select>
            </label>
            <p className="muted">{activeCredentialType.summary}</p>
            {profileRequiresUsername ? (
              <label>
                Username *
                <input
                  value={profileForm.username}
                  required
                  onChange={(event) =>
                    setProfileForm({
                      ...profileForm,
                      username: event.target.value,
                    })
                  }
                />
              </label>
            ) : null}
            <label>
              Provider reference *
              <input
                value={profileForm.provider_reference}
                required
                onChange={(event) =>
                  setProfileForm({
                    ...profileForm,
                    provider_reference: event.target.value,
                  })
                }
              />
            </label>
            <label>
              Supported transports *
              <select
                multiple
                value={profileForm.transport_types}
                onChange={(event) => {
                  const value = Array.from(
                    event.target.selectedOptions,
                    (option) => option.value,
                  )
                  setProfileForm({
                    ...profileForm,
                    transport_types: value,
                  })
                }}
              >
                <option value="ssh">ssh</option>
                <option value="snmp">snmp</option>
                <option value="telnet">telnet</option>
                <option value="http">http</option>
                <option value="https">https</option>
              </select>
            </label>
            <div className="inline-actions">
              <button type="submit" disabled={creatingProfile}>
                {creatingProfile ? 'Saving…' : 'Save profile'}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setShowProfileComposer(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      ) : null}

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

      {deviceResults.length > 0 ? (
        <section className="card">
          <h3>Discovered devices ({deviceResults.length})</h3>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Address</th>
                  <th>Vendor</th>
                  <th>State</th>
                  <th>Transport</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {deviceResults.map((result) => (
                  <tr key={result.result_id}>
                    <td>{result.address}</td>
                    <td>{result.vendor || 'Unknown'}</td>
                    <td>{result.state}</td>
                    <td>{result.selected_transport || 'Not selected'}</td>
                    <td>{result.failure_code || 'Discovered'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}
