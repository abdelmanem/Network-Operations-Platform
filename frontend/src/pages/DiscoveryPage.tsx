import { useEffect, useMemo, useState } from 'react'
import {
  createDiscoveryApiJob,
  createDiscoveryCredentialProfile,
  createDiscoveryTarget,
  getDiscoveryApiJob,
  getDiscoveryEvidence,
  getDiscoveryDeviceResults,
  listDiscoveryCredentialProfiles,
  listDiscoveryTargets,
  testDiscoveryCredentialProfile,
} from '../api/discovery'
import type {
  CredentialProfileResponse,
  CredentialProfileTestResponse,
  DiscoveryApiJobResponse,
  DiscoveryEvidenceResponse,
  DiscoveryDeviceResultResponse,
  DiscoveryTargetResponse,
} from '../types/api'
import './DiscoveryPage.css'

const terminalStates = new Set([
  'succeeded',
  'failed',
  'timed_out',
  'cancelled',
])

type CredentialVisualState = 'success' | 'warning' | 'error' | 'info'

type CredentialTestState = {
  label: string
  summary: string
  action: string
  visualState: CredentialVisualState
}

const credentialTypeHelp: Record<
  string,
  {
    label: string
    summary: string
    transport_types: string[]
  }
> = {
  ssh_password: {
    label: 'SSH password',
    summary:
      'Username and password authentication over SSH. The secret is resolved only at execution time.',
    transport_types: ['ssh'],
  },
  ssh_key: {
    label: 'SSH key',
    summary:
      'SSH key-based authentication. Private key material is resolved only at execution time.',
    transport_types: ['ssh'],
  },
  snmp_v2c: {
    label: 'SNMPv2c community',
    summary:
      'SNMPv2c community-based discovery using the configured secret reference.',
    transport_types: ['snmp'],
  },
  snmp_v3: {
    label: 'SNMPv3',
    summary:
      'SNMPv3 authentication material resolved from the configured secret provider.',
    transport_types: ['snmp'],
  },
}

const platformLabels: Record<string, string> = {
  'cisco-iosxe': 'Cisco IOS-XE',
  'cisco-ios': 'Cisco IOS',
}

const scopeLabels: Record<string, string> = {
  single_device: 'Single device',
  ip_range: 'IP range',
  cidr_network: 'CIDR network',
}

const transportLabels: Record<string, string> = {
  netmiko: 'SSH',
  ssh: 'SSH',
  snmp: 'SNMP',
  http: 'HTTP',
  telnet: 'Telnet',
  https: 'HTTPS',
}

function formatPlatform(value: string | null | undefined) {
  if (!value) return 'Auto-detect'
  return platformLabels[value] || value
}

function formatScope(value: string | null | undefined) {
  if (!value) return 'Single device'
  return scopeLabels[value] || value.replaceAll('_', ' ')
}

function formatTransport(value: string | null | undefined) {
  if (!value) return '—'
  return transportLabels[value.toLowerCase()] || value.toUpperCase()
}

function targetAddress(target: DiscoveryTargetResponse) {
  return target.address || target.scope_cidr || 'Network scope'
}

function getCredentialTestState(
  result: CredentialProfileTestResponse,
): CredentialTestState {
  const status = (result.status || '').toLowerCase()
  const message = (result.message || '').toLowerCase()

  if (
    status === 'success' &&
    !message.includes('authentication failed') &&
    !message.includes('connection failed') &&
    !message.includes('timed out') &&
    !message.includes('timeout')
  ) {
    return {
      label: 'Secret configured',
      summary:
        'The configured secret reference resolved successfully.',
      action: 'Continue with device validation.',
      visualState: 'success',
    }
  }

  if (status === 'unsupported_transport') {
    return {
      label: 'Unsupported transport',
      summary:
        'The selected transport is not supported for this credential profile.',
      action: 'Select a supported transport/profile.',
      visualState: 'info',
    }
  }

  if (status === 'invalid_credential_profile') {
    if (
      message.includes('no secret was resolved') ||
      message.includes('secret was not found') ||
      message.includes('no secret')
    ) {
      return {
        label: 'Secret missing',
        summary:
          'The secret reference is configured, but no secret was found for it.',
        action: 'Configure the referenced secret before retrying.',
        visualState: 'warning',
      }
    }

    return {
      label: 'Invalid credential profile',
      summary:
        'The profile does not satisfy the credential contract required by the selected transport.',
      action: 'Correct the profile configuration and retry.',
      visualState: 'error',
    }
  }

  if (message.includes('authentication failed')) {
    return {
      label: 'Authentication failed',
      summary: 'The device rejected the supplied credentials.',
      action: 'Verify the username and credential reference.',
      visualState: 'error',
    }
  }

  if (
    message.includes('connection failed') ||
    message.includes('connection refused') ||
    message.includes('network unreachable')
  ) {
    return {
      label: 'Connection failed',
      summary: 'The connection could not be established successfully.',
      action: 'Verify the device address and network reachability.',
      visualState: 'error',
    }
  }

  if (message.includes('timeout') || message.includes('timed out')) {
    return {
      label: 'Timeout',
      summary:
        'The credential test did not complete within the configured timeout.',
      action:
        'Verify reachability and timeout conditions before retrying.',
      visualState: 'warning',
    }
  }

  return {
    label: 'Credential test result',
    summary: result.message || 'Credential test completed.',
    action: 'Review the result and retry when appropriate.',
    visualState: 'info',
  }
}

function StatusIcon({ state }: { state: CredentialVisualState }) {
  if (state === 'success') return <>✓</>
  if (state === 'warning') return <>!</>
  if (state === 'error') return <>×</>
  return <>i</>
}

function TransportBadge({ transport }: { transport: string }) {
  return (
    <span className="discovery-transport-badge">
      {formatTransport(transport)}
    </span>
  )
}

function CredentialResult({
  result,
}: {
  result: CredentialProfileTestResponse
}) {
  const state = getCredentialTestState(result)

  return (
    <div
      className={`credential-result credential-${state.visualState}`}
      role="status"
    >
      <div className="credential-result-icon">
        <StatusIcon state={state.visualState} />
      </div>

      <div className="credential-result-body">
        <div className="credential-result-title">
          <div className="status-pill">{state.label}</div>
        </div>

        <p className="credential-result-summary">{state.summary}</p>

        <div className="credential-result-action">
          <em>Next action</em>: {state.action}
        </div>

        {result.message ? (
          <details className="credential-result-details">
            <summary>Technical details</summary>
            <pre>{result.message}</pre>
          </details>
        ) : null}
      </div>
    </div>
  )
}

function PageStatus({
  job,
  starting,
}: {
  job: DiscoveryApiJobResponse | null
  starting: boolean
}) {
  if (starting) {
    return (
      <div className="discovery-status-bar">
        <span className="discovery-status-indicator discovery-status-running">
          Starting
        </span>
        <span className="discovery-status-meta">
          Preparing discovery job…
        </span>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="discovery-status-bar">
        <span className="discovery-status-indicator discovery-status-ready">
          Ready
        </span>
        <span className="discovery-status-meta">
          Select a target and start discovery when credentials are validated.
        </span>
      </div>
    )
  }

  const running = !terminalStates.has(job.status)

  return (
    <div className="discovery-status-bar">
      <span
        className={`discovery-status-indicator discovery-status-${job.status}`}
      >
        {running ? 'Running' : job.status.replaceAll('_', ' ')}
      </span>
      <span className="discovery-status-meta">
        Job {job.job_id.slice(0, 8)}…
        {job.selected_platform
          ? ` · ${formatPlatform(job.selected_platform)}`
          : ''}
        {job.selected_transport
          ? ` · ${formatTransport(job.selected_transport)}`
          : ''}
      </span>
    </div>
  )
}

function OverviewPanel({
  targets,
  selectedTarget,
  profiles,
  job,
}: {
  targets: DiscoveryTargetResponse[]
  selectedTarget: DiscoveryTargetResponse | null
  profiles: CredentialProfileResponse[]
  job: DiscoveryApiJobResponse | null
}) {
  const activeJobs =
    job && !terminalStates.has(job.status) ? 1 : 0

  return (
    <section className="discovery-panel discovery-overview">
      <div className="discovery-panel-header">
        <div>
          <h2>Discovery overview</h2>
          <p className="discovery-panel-subtitle">
            Current inventory and operational status
          </p>
        </div>
      </div>

      <div className="discovery-overview-grid">
        <div className="discovery-overview-item">
          <span>Targets</span>
          <strong>{targets.length}</strong>
        </div>
        <div className="discovery-overview-item">
          <span>Credential profiles</span>
          <strong>{profiles.length}</strong>
        </div>
        <div className="discovery-overview-item">
          <span>Active jobs</span>
          <strong>{activeJobs}</strong>
        </div>
        <div className="discovery-overview-item">
          <span>Selected target</span>
          <strong>
            {selectedTarget?.identifier || 'None'}
          </strong>
        </div>
      </div>
    </section>
  )
}

function TargetSidebar({
  targets,
  selectedTargetId,
  loading,
  onSelect,
  onAddTarget,
}: {
  targets: DiscoveryTargetResponse[]
  selectedTargetId: string
  loading: boolean
  onSelect: (id: string) => void
  onAddTarget: () => void
}) {
  return (
    <aside className="discovery-panel discovery-targets-sidebar">
      <div className="discovery-panel-header">
        <h2>Targets</h2>
      </div>

      {loading ? (
        <div className="discovery-loading">
          <span className="discovery-spinner" />
          Loading targets…
        </div>
      ) : null}

      {!loading && targets.length === 0 ? (
        <div className="discovery-empty-state">
          <div className="discovery-empty-icon">⌁</div>
          <strong>No discovery targets</strong>
          <span className="muted">
            Add a device or network scope to begin discovery.
          </span>
          <button
            type="button"
            className="discovery-btn discovery-btn-secondary discovery-btn-compact"
            onClick={onAddTarget}
          >
            Add target
          </button>
        </div>
      ) : (
        <div className="discovery-targets-list">
          {targets.map((target) => {
            const selected = target.target_id === selectedTargetId

            return (
              <button
                key={target.target_id}
                type="button"
                className={`discovery-target-item ${
                  selected ? 'discovery-target-item-selected' : ''
                }`}
                onClick={() => onSelect(target.target_id)}
              >
                <span className="discovery-target-dot" />
                <span className="discovery-target-item-main">
                  <span className="discovery-target-item-name">
                    {target.identifier}
                  </span>
                  <span className="discovery-target-item-address">
                    {targetAddress(target)}
                  </span>
                  <span className="discovery-target-item-meta">
                    <span>
                      {formatPlatform(target.platform_hint)}
                    </span>
                    {target.preferred_transport ? (
                      <TransportBadge
                        transport={target.preferred_transport}
                      />
                    ) : null}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      )}

      {targets.length > 0 ? (
        <div className="discovery-targets-footer">
          <button
            type="button"
            className="discovery-btn discovery-btn-ghost"
            onClick={onAddTarget}
          >
            + Add target
          </button>
        </div>
      ) : null}
    </aside>
  )
}

type ProfileWithDetails = CredentialProfileResponse & {
  username?: string | null
  vendor?: string | null
  platform?: string | null
}

function getSecretStatus(profile: ProfileWithDetails | null, profileTestResult: CredentialProfileTestResponse | null) {
  if (!profile || !profile.provider_reference) {
    return {
      label: 'Missing',
      className: 'discovery-secret-missing',
    }
  }

  if (!profileTestResult) {
    return {
      label: 'Not tested',
      className: 'discovery-secret-pending',
    }
  }

  const status = getCredentialTestState(profileTestResult)
  return {
    label:
      status.label === 'Secret missing' ||
      status.label === 'Invalid credential profile' ||
      status.label === 'Unsupported transport'
        ? 'Missing'
        : 'Configured',
    className:
      status.label === 'Secret missing' ||
      status.label === 'Invalid credential profile' ||
      status.label === 'Unsupported transport'
        ? 'discovery-secret-missing'
        : 'discovery-secret-configured',
  }
}

function SelectedTargetPanel({
  target,
  profile,
  profiles,
  profileTestResult,
  testingCredential,
  onTestCredential,
  onManageProfiles,
}: {
  target: DiscoveryTargetResponse | null
  profile: ProfileWithDetails | null
  profiles: ProfileWithDetails[]
  profileTestResult: CredentialProfileTestResponse | null
  testingCredential: boolean
  onTestCredential: () => void
  onManageProfiles: () => void
}) {
  const transport =
    profile?.transport_types[0] ||
    target?.preferred_transport ||
    'ssh'
  const secretStatus = getSecretStatus(profile, profileTestResult)

  if (!target) {
    const fallbackProfile = profiles[0] || null
    const fallbackTransport =
      fallbackProfile?.transport_types[0] || 'ssh'

    return (
      <section className="discovery-panel discovery-target-detail">
        <div className="discovery-target-empty">
          <div className="discovery-empty-icon">⌁</div>
          <h2>Select a target</h2>
          <p className="muted">
            Choose a discovery target from the sidebar to view
            configuration and run discovery.
          </p>
        </div>

        {profiles.length === 0 ? (
          <div className="discovery-credential-section">
            <p className="muted">
              No credential profiles are configured. Create a profile
              before adding targets.
            </p>
            <button
              type="button"
              className="discovery-btn discovery-btn-secondary"
              onClick={onManageProfiles}
            >
              Create credential profile
            </button>
          </div>
        ) : (
          <div className="discovery-credential-section">
            <h3>Credential profile</h3>
            <div className="discovery-credential-select">
              <label htmlFor="preview-credential-profile">
                Credential profile
                <select
                  id="preview-credential-profile"
                  value={fallbackProfile?.profile_id || ''}
                  disabled
                >
                  {profiles.map((item) => (
                    <option
                      key={item.profile_id}
                      value={item.profile_id}
                    >
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {fallbackProfile ? (
              <>
                <div className="discovery-credential-details">
                  <div className="discovery-credential-detail">
                    <span>Username</span>
                    <strong>{fallbackProfile.username || '—'}</strong>
                  </div>
                  <div className="discovery-credential-detail">
                    <span>Transport</span>
                    <strong>
                      {formatTransport(fallbackTransport)}
                    </strong>
                  </div>
                  <div className="discovery-credential-detail">
                    <span>Secret</span>
                    <strong className={secretStatus.className}>
                      {secretStatus.label}
                    </strong>
                  </div>
                </div>
                <div className="discovery-credential-actions">
                  <button
                    type="button"
                    className="discovery-btn discovery-btn-secondary discovery-btn-compact"
                    disabled={testingCredential}
                    onClick={onTestCredential}
                  >
                    {testingCredential ? 'Testing…' : 'Test credential'}
                  </button>
                  <button
                    type="button"
                    className="discovery-btn discovery-btn-ghost discovery-btn-compact"
                    onClick={onManageProfiles}
                  >
                    Manage profiles
                  </button>
                </div>
                <p className="discovery-security-note">
                  Environment secret provider: secret material is resolved by
                  the backend at execution time and is never stored in the
                  credential profile. This is not the password.
                </p>
              </>
            ) : null}
            {profileTestResult ? (
              <CredentialResult result={profileTestResult} />
            ) : null}
          </div>
        )}
      </section>
    )
  }

  return (
    <section className="discovery-panel discovery-target-detail">
      <div className="discovery-target-detail-header">
        <div className="discovery-target-title">
          <h2>{target.identifier}</h2>
          <div className="discovery-target-address">
            {targetAddress(target)}
          </div>
        </div>
        <span className="discovery-platform-badge">
          {formatPlatform(target.platform_hint)}
        </span>
      </div>

      <div className="discovery-facts-grid">
        <div className="discovery-fact">
          <span>Target</span>
          <strong>{target.identifier}</strong>
        </div>
        <div className="discovery-fact">
          <span>Address</span>
          <strong>{targetAddress(target)}</strong>
        </div>
        <div className="discovery-fact">
          <span>Platform</span>
          <strong>{formatPlatform(target.platform_hint)}</strong>
        </div>
        <div className="discovery-fact">
          <span>Scope</span>
          <strong>{formatScope(target.scope_type)}</strong>
        </div>
        <div className="discovery-fact">
          <span>Transport</span>
          <strong>{formatTransport(transport)}</strong>
        </div>
        <div className="discovery-fact">
          <span>Credential</span>
          <strong>{profile?.name || 'Not configured'}</strong>
        </div>
      </div>

      <div className="discovery-credential-section">
        <h3>Credential profile</h3>

        {profiles.length === 0 ? (
          <>
            <p className="muted">
              No credential profiles are configured.
            </p>
            <button
              type="button"
              className="discovery-btn discovery-btn-secondary"
              onClick={onManageProfiles}
            >
              Create credential profile
            </button>
          </>
        ) : (
          <>
            <div className="discovery-credential-select">
              <label htmlFor="selected-credential-profile">
                Credential profile
                <select
                  id="selected-credential-profile"
                  value={profile?.profile_id || ''}
                  disabled
                >
                  <option value="">Select credential profile</option>
                  {profiles.map((item) => (
                    <option
                      key={item.profile_id}
                      value={item.profile_id}
                    >
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {profile ? (
              <>
                <div className="discovery-credential-details">
                  <div className="discovery-credential-detail">
                    <span>Username</span>
                    <strong>
                      {profile.username || '—'}
                    </strong>
                  </div>
                  <div className="discovery-credential-detail">
                    <span>Transport</span>
                    <strong>{formatTransport(transport)}</strong>
                  </div>
                  <div className="discovery-credential-detail">
                    <span>Secret</span>
                    <strong className={secretStatus.className}>
                      {secretStatus.label}
                    </strong>
                  </div>
                </div>

                {profile.provider_reference ? (
                  <details className="discovery-secret-advanced">
                    <summary>Advanced / Secret provider details</summary>
                    <div className="discovery-credential-details">
                      <div className="discovery-credential-detail">
                        <span>Secret provider</span>
                        <strong>Environment</strong>
                      </div>
                      <div className="discovery-credential-detail">
                        <span>Provider reference</span>
                        <code>{profile.provider_reference}</code>
                      </div>
                      <div className="discovery-credential-detail">
                        <span>Secret value</span>
                        <strong>Never displayed</strong>
                      </div>
                    </div>
                    <p className="discovery-security-note">
                      The secret value is resolved by the backend at runtime
                      and is never stored in or returned to the frontend.
                    </p>
                  </details>
                ) : null}

                <p className="discovery-security-note">
                  Environment secret provider: secret material is resolved by
                  the backend at execution time and is never stored in the
                  credential profile. This is not the password.
                </p>

                <div className="discovery-credential-actions">
                  <button
                    type="button"
                    className="discovery-btn discovery-btn-secondary discovery-btn-compact"
                    disabled={testingCredential}
                    onClick={onTestCredential}
                  >
                    {testingCredential ? 'Testing…' : 'Test credential'}
                  </button>
                  <button
                    type="button"
                    className="discovery-btn discovery-btn-ghost discovery-btn-compact"
                    onClick={onManageProfiles}
                  >
                    Manage profiles
                  </button>
                </div>
              </>
            ) : null}
          </>
        )}

        {profileTestResult ? (
          <CredentialResult result={profileTestResult} />
        ) : null}
      </div>

      <div className="discovery-plan">
        <h3>Discovery plan</h3>
        <div className="discovery-plan-grid">
          <div className="discovery-fact">
            <span>Scope</span>
            <strong>{formatScope(target.scope_type)}</strong>
          </div>
          <div className="discovery-fact">
            <span>Vendor</span>
            <strong>{target.vendor || profile?.vendor || 'Cisco'}</strong>
          </div>
          <div className="discovery-fact">
            <span>Platform</span>
            <strong>{formatPlatform(target.platform_hint)}</strong>
          </div>
          <div className="discovery-fact">
            <span>Transport</span>
            <strong>{formatTransport(transport)}</strong>
          </div>
          <div className="discovery-fact">
            <span>Credential</span>
            <strong>{profile?.name || 'Not configured'}</strong>
          </div>
          <div className="discovery-fact">
            <span>Fallback</span>
            <strong>SNMP / HTTP</strong>
          </div>
        </div>
      </div>
    </section>
  )
}

function DiscoveryExecutionPanel({
  target,
  job,
  starting,
  onStartDiscovery,
}: {
  target: DiscoveryTargetResponse | null
  job: DiscoveryApiJobResponse | null
  starting: boolean
  onStartDiscovery: () => void
}) {
  const running = Boolean(job) && !terminalStates.has(job?.status || '')

  return (
    <section className="discovery-panel discovery-execution">
      <div className="discovery-panel-header">
        <div>
          <h2>Discovery execution</h2>
          {target ? (
            <p className="discovery-panel-subtitle">
              Selected target: {target.identifier} ·{' '}
              {targetAddress(target)}
            </p>
          ) : (
            <p className="discovery-panel-subtitle">
              Select a target to start discovery
            </p>
          )}
        </div>
        <button
          type="button"
          className="discovery-btn discovery-btn-primary discovery-btn-compact"
          disabled={!target || starting || running}
          onClick={onStartDiscovery}
        >
          {starting
            ? 'Starting…'
            : running
              ? 'Running…'
              : 'Start discovery'}
        </button>
      </div>

      {job ? (
        <div
          className={`discovery-execution-body discovery-execution-${job.status}`}
        >
          <div className="discovery-execution-banner">
            <strong>{job.status.replaceAll('_', ' ')}</strong>
          </div>

          <dl className="discovery-execution-meta">
            <div>
              <dt>Job ID</dt>
              <dd>{job.job_id}</dd>
            </div>
            {job.selected_platform ? (
              <div>
                <dt>Collector family</dt>
                <dd>{formatPlatform(job.selected_platform)}</dd>
              </div>
            ) : null}
            {job.selected_transport ? (
              <div>
                <dt>Transport</dt>
                <dd>{formatTransport(job.selected_transport)}</dd>
              </div>
            ) : null}
            {job.attempts > 0 ? (
              <div>
                <dt>Attempts</dt>
                <dd>{job.attempts}</dd>
              </div>
            ) : null}
          </dl>

          {job.error_code || job.error_message ? (
            <div className="discovery-execution-error">
              {job.error_code ? (
                <strong>{job.error_code}: </strong>
              ) : null}
              {job.error_message}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function resultBadgeClass(result: DiscoveryDeviceResultResponse) {
  if (result.failure_code) {
    const code = result.failure_code.toLowerCase()
    if (code.includes('auth')) return 'discovery-result-authentication_failed'
    if (code.includes('timeout') || code.includes('timed_out')) {
      return 'discovery-result-timeout'
    }
    return 'discovery-result-failed'
  }

  const state = (result.state || '').toLowerCase()
  if (state.includes('fail')) return 'discovery-result-failed'
  if (state.includes('timeout') || state.includes('timed_out')) {
    return 'discovery-result-timeout'
  }

  return 'discovery-result-discovered'
}

function resultBadgeLabel(result: DiscoveryDeviceResultResponse) {
  if (result.failure_code) {
    const code = result.failure_code.toLowerCase()
    if (code.includes('auth')) return 'Authentication failed'
    if (code.includes('timeout')) return 'Timeout'
    return result.failure_code.replaceAll('_', ' ')
  }

  if (result.state) {
    return result.state.replaceAll('_', ' ')
  }

  return 'Discovered'
}

function DiscoveryResultsPanel({
  deviceResults,
  evidence,
}: {
  deviceResults: DiscoveryDeviceResultResponse[]
  evidence: DiscoveryEvidenceResponse[]
}) {
  if (deviceResults.length === 0 && evidence.length === 0) {
    return null
  }

  return (
    <section className="discovery-panel discovery-results">
      <div className="discovery-panel-header">
        <div>
          <h2>Discovery results</h2>
          <p className="discovery-results-summary">
            {deviceResults.length} device
            {deviceResults.length !== 1 ? 's' : ''} discovered
          </p>
        </div>
      </div>

      {deviceResults.length > 0 ? (
        <div className="discovery-table-wrap">
          <table className="discovery-table">
            <thead>
              <tr>
                <th>Address</th>
                <th>Hostname</th>
                <th>Vendor</th>
                <th>Model</th>
                <th>Platform</th>
                <th>State</th>
                <th>Transport</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {deviceResults.map((result) => (
                <tr key={result.result_id}>
                  <td>
                    <code>{result.address}</code>
                  </td>
                  <td>{result.hostname || '—'}</td>
                  <td>{result.vendor || 'Unknown'}</td>
                  <td>{result.model || '—'}</td>
                  <td>{result.platform || '—'}</td>
                  <td>{result.state.replaceAll('_', ' ')}</td>
                  <td>
                    {result.selected_transport
                      ? formatTransport(result.selected_transport)
                      : '—'}
                  </td>
                  <td>
                    <span
                      className={`discovery-result-badge ${resultBadgeClass(result)}`}
                    >
                      {resultBadgeLabel(result)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {evidence.length > 0 ? (
        <div className="discovery-evidence">
          <h4>Evidence</h4>
          {evidence.map((record) => (
            <details
              key={record.evidence_id}
              className="discovery-evidence-item"
            >
              <summary>
                <span>{record.command_or_probe}</span>
                <code>
                  {record.content_hash.slice(0, 12)}…
                  {record.captured_at
                    ? ` · ${new Date(record.captured_at).toLocaleString()}`
                    : ''}
                </code>
              </summary>
              <pre>{JSON.stringify(record.payload, null, 2)}</pre>
            </details>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function AddTargetModal({
  form,
  profiles,
  saving,
  onChange,
  onSubmit,
  onCancel,
  onCreateProfile,
}: {
  form: {
    scope_type: 'single_device' | 'ip_range' | 'cidr_network'
    identifier: string
    address: string
    scope_end: string
    scope_cidr: string
    credential_profile_id: string
    platform_hint: string
    preferred_transport: string
  }
  profiles: CredentialProfileResponse[]
  saving: boolean
  onChange: (next: Partial<typeof form>) => void
  onSubmit: (event: React.FormEvent) => void
  onCancel: () => void
  onCreateProfile: () => void
}) {
  return (
    <div className="discovery-modal-backdrop">
      <div
        className="discovery-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-target-title"
      >
        <form onSubmit={onSubmit}>
          <div className="discovery-modal-header">
            <div>
              <div className="discovery-eyebrow">CONFIGURATION</div>
              <h2 id="add-target-title">Add discovery target</h2>
              <p className="muted">
                Define the device or network scope to discover.
              </p>
            </div>
            <button
              type="button"
              className="discovery-modal-close"
              onClick={onCancel}
              aria-label="Close"
            >
              ×
            </button>
          </div>

          <div className="discovery-modal-body">
            <div className="discovery-form-section">
              <h3>Target identity</h3>
              <div className="discovery-form-grid">
                <label className="discovery-form-field discovery-form-field-wide">
                  Target name
                  <input
                    value={form.identifier}
                    required
                    placeholder="e.g. Core-Switch-01"
                    onChange={(event) =>
                      onChange({ identifier: event.target.value })
                    }
                  />
                </label>

                {form.scope_type !== 'cidr_network' ? (
                  <label className="discovery-form-field">
                    {form.scope_type === 'ip_range'
                      ? 'Start address'
                      : 'Management address'}
                    <input
                      value={form.address}
                      required
                      placeholder="10.10.10.10"
                      onChange={(event) =>
                        onChange({ address: event.target.value })
                      }
                    />
                  </label>
                ) : null}

                {form.scope_type === 'ip_range' ? (
                  <label className="discovery-form-field">
                    End address
                    <input
                      value={form.scope_end}
                      required
                      placeholder="10.10.10.50"
                      onChange={(event) =>
                        onChange({ scope_end: event.target.value })
                      }
                    />
                  </label>
                ) : null}

                {form.scope_type === 'cidr_network' ? (
                  <label className="discovery-form-field discovery-form-field-wide">
                    CIDR network
                    <input
                      value={form.scope_cidr}
                      required
                      placeholder="10.10.20.0/24"
                      onChange={(event) =>
                        onChange({ scope_cidr: event.target.value })
                      }
                    />
                  </label>
                ) : null}
              </div>
            </div>

            <div className="discovery-form-section">
              <h3>Discovery scope</h3>
              <div className="discovery-scope-options">
                {[
                  ['single_device', 'Single device', 'One management address'],
                  ['ip_range', 'IP range', 'Continuous address range'],
                  ['cidr_network', 'CIDR network', 'Network prefix'],
                ].map(([value, label, description]) => (
                  <button
                    key={value}
                    type="button"
                    className={`discovery-scope-option ${
                      form.scope_type === value
                        ? 'discovery-scope-option-selected'
                        : ''
                    }`}
                    onClick={() =>
                      onChange({
                        scope_type: value as typeof form.scope_type,
                      })
                    }
                  >
                    <strong>{label}</strong>
                    <span>{description}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="discovery-form-section">
              <h3>Platform</h3>
              <div className="discovery-form-grid">
                <label className="discovery-form-field">
                  Platform
                  <select
                    value={form.platform_hint}
                    onChange={(event) =>
                      onChange({ platform_hint: event.target.value })
                    }
                  >
                    <option value="cisco-iosxe">Cisco IOS-XE</option>
                    <option value="cisco-ios">Cisco IOS</option>
                  </select>
                </label>

                <label className="discovery-form-field">
                  Preferred transport
                  <select
                    value={form.preferred_transport}
                    onChange={(event) =>
                      onChange({
                        preferred_transport: event.target.value,
                      })
                    }
                  >
                    <option value="netmiko">SSH / Netmiko</option>
                    <option value="snmp">SNMP</option>
                    <option value="http">HTTP</option>
                  </select>
                </label>
              </div>
            </div>

            <div className="discovery-form-section">
              <h3>Credentials</h3>
              {profiles.length === 0 ? (
                <>
                  <p className="muted">
                    No credential profiles are configured.
                  </p>
                  <button
                    type="button"
                    className="discovery-btn discovery-btn-secondary"
                    onClick={onCreateProfile}
                  >
                    Create credential profile
                  </button>
                </>
              ) : (
                <label
                  className="discovery-form-field discovery-form-field-wide"
                  htmlFor="add-target-credential-profile"
                >
                  Credential profile
                  <select
                    id="add-target-credential-profile"
                    value={form.credential_profile_id}
                    required
                    onChange={(event) =>
                      onChange({
                        credential_profile_id: event.target.value,
                      })
                    }
                  >
                    <option value="">Select credential profile</option>
                    {profiles.map((item) => (
                      <option
                        key={item.profile_id}
                        value={item.profile_id}
                      >
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          </div>

          <div className="discovery-modal-footer">
            <button
              type="button"
              className="discovery-btn discovery-btn-secondary"
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="discovery-btn discovery-btn-primary"
              disabled={
                saving ||
                profiles.length === 0 ||
                !form.credential_profile_id
              }
            >
              {saving ? 'Saving target…' : 'Save target'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CredentialProfileModal({
  form,
  creating,
  onChange,
  onSubmit,
  onCancel,
}: {
  form: {
    name: string
    description: string
    vendor: string
    platform: string
    credential_type: string
    username: string
    transport_types: string[]
    provider_reference: string
  }
  creating: boolean
  onChange: (next: Partial<typeof form>) => void
  onSubmit: (event: React.FormEvent) => void
  onCancel: () => void
}) {
  const type =
    credentialTypeHelp[form.credential_type] ||
    credentialTypeHelp.ssh_password

  const requiresUsername =
    form.credential_type === 'ssh_password' ||
    form.credential_type === 'ssh_key' ||
    form.credential_type === 'snmp_v3'

  const allowedTransports = [
    'ssh',
    'snmp',
    'telnet',
    'http',
    'https',
  ]

  return (
    <div className="discovery-modal-backdrop">
      <div
        className="discovery-modal discovery-modal-wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-profile-title"
      >
        <form onSubmit={onSubmit}>
          <div className="discovery-modal-header">
            <div>
              <div className="discovery-eyebrow">CREDENTIALS</div>
              <h2 id="create-profile-title">
                Create credential profile
              </h2>
              <p className="muted">
                Store authentication metadata without storing secret
                material.
              </p>
            </div>
            <button
              type="button"
              className="discovery-modal-close"
              onClick={onCancel}
              aria-label="Close"
            >
              ×
            </button>
          </div>

          <div className="discovery-modal-body">
            <div className="discovery-info-panel">
              <span>🔒</span>
              <div>
                <strong>Environment secret provider</strong>
                <p className="muted">
                  Credential secrets are not stored here. This profile
                  stores only metadata and a provider reference. The
                  backend resolves the secret at runtime. This is not
                  the password.
                </p>
              </div>
            </div>

            <div className="discovery-form-section">
              <h3>Profile details</h3>
              <div className="discovery-form-grid">
                <label className="discovery-form-field discovery-form-field-wide">
                  Profile name
                  <input
                    value={form.name}
                    required
                    placeholder="e.g. Cisco SSH Production"
                    onChange={(event) =>
                      onChange({ name: event.target.value })
                    }
                  />
                </label>

                <label className="discovery-form-field discovery-form-field-wide">
                  Description
                  <input
                    value={form.description}
                    placeholder="Optional description"
                    onChange={(event) =>
                      onChange({ description: event.target.value })
                    }
                  />
                </label>

                <label className="discovery-form-field">
                  Vendor
                  <input
                    value={form.vendor}
                    required
                    onChange={(event) =>
                      onChange({ vendor: event.target.value })
                    }
                  />
                </label>

                <label className="discovery-form-field">
                  Platform
                  <input
                    value={form.platform}
                    required
                    onChange={(event) =>
                      onChange({ platform: event.target.value })
                    }
                  />
                </label>
              </div>
            </div>

            <div className="discovery-form-section">
              <h3>Authentication</h3>
              <label className="discovery-form-field discovery-form-field-wide">
                Credential type
                <select
                  value={form.credential_type}
                  onChange={(event) => {
                    const next = event.target.value
                    onChange({
                      credential_type: next,
                      transport_types:
                        credentialTypeHelp[next]?.transport_types || [
                          'ssh',
                        ],
                    })
                  }}
                >
                  <option value="ssh_password">SSH password</option>
                  <option value="ssh_key">SSH key</option>
                  <option value="snmp_v2c">SNMPv2c community</option>
                  <option value="snmp_v3">SNMPv3</option>
                </select>
              </label>

              <p className="muted">{type.summary}</p>

              {requiresUsername ? (
                <label className="discovery-form-field discovery-form-field-wide">
                  Username
                  <input
                    value={form.username}
                    required
                    placeholder="admin"
                    onChange={(event) =>
                      onChange({ username: event.target.value })
                    }
                  />
                </label>
              ) : null}

              <label className="discovery-form-field discovery-form-field-wide">
                Secret reference
                <input
                  value={form.provider_reference}
                  required
                  placeholder="TEST_CISCO_SSH_PASSWORD"
                  onChange={(event) =>
                    onChange({
                      provider_reference: event.target.value,
                    })
                  }
                />
              </label>
            </div>

            <div className="discovery-form-section">
              <h3>Transport</h3>
              <div className="discovery-transport-chips">
                {allowedTransports.map((transport) => {
                  const selected =
                    form.transport_types.includes(transport)
                  const typeTransports = type.transport_types
                  const disabled =
                    typeTransports.length === 1 &&
                    !typeTransports.includes(transport)

                  return (
                    <button
                      key={transport}
                      type="button"
                      disabled={disabled}
                      className={`discovery-transport-chip ${
                        selected
                          ? 'discovery-transport-chip-selected'
                          : ''
                      }`}
                      onClick={() => {
                        if (disabled) return

                        const next = selected
                          ? form.transport_types.filter(
                              (item) => item !== transport,
                            )
                          : [...form.transport_types, transport]

                        onChange({ transport_types: next })
                      }}
                    >
                      {selected ? '✓ ' : ''}
                      {transport.toUpperCase()}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          <div className="discovery-modal-footer">
            <button
              type="button"
              className="discovery-btn discovery-btn-secondary"
              onClick={onCancel}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="discovery-btn discovery-btn-primary"
              disabled={
                creating ||
                !form.name.trim() ||
                !form.provider_reference.trim() ||
                form.transport_types.length === 0
              }
            >
              {creating ? 'Saving…' : 'Save profile'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

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
  const [testingCredential, setTestingCredential] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAddTargetModal, setShowAddTargetModal] = useState(false)
  const [showProfileComposer, setShowProfileComposer] = useState(false)
  const [profileTestResult, setProfileTestResult] =
    useState<CredentialProfileTestResponse | null>(null)

  const [targetForm, setTargetForm] = useState({
    scope_type: 'single_device' as
      | 'single_device'
      | 'ip_range'
      | 'cidr_network',
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

  const selectedTarget = useMemo(
    () =>
      targets.find((target) => target.target_id === selectedTargetId) ||
      null,
    [targets, selectedTargetId],
  )

  const selectedProfile = useMemo(() => {
    const profileId =
      selectedTarget?.credential_profile_id ||
      targetForm.credential_profile_id

    return (
      profiles.find((profile) => profile.profile_id === profileId) ||
      null
    )
  }, [profiles, selectedTarget, targetForm.credential_profile_id])

  async function loadTargets() {
    setLoading(true)
    setError(null)

    try {
      const data = await listDiscoveryTargets()
      setTargets(data)

      if (!selectedTargetId && data[0]) {
        setSelectedTargetId(data[0].target_id)
      }
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
    if (!job || terminalStates.has(job.status)) {
      return
    }

    const timer = window.setInterval(async () => {
      try {
        const updated = await getDiscoveryApiJob(job.job_id)
        setJob(updated)

        setDeviceResults(
          await getDiscoveryDeviceResults(updated.job_id),
        )

        if (terminalStates.has(updated.status)) {
          setEvidence(await getDiscoveryEvidence(updated.job_id))
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to poll discovery job.',
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
      const tenantId =
        window.localStorage.getItem('tenant-id') || 'default'

      if (!targetForm.credential_profile_id) {
        throw new Error(
          'A credential profile is required before creating a target.',
        )
      }

      const created = await createDiscoveryTarget({
        ...targetForm,
        address:
          targetForm.scope_type === 'cidr_network'
            ? null
            : targetForm.address,
        scope_end:
          targetForm.scope_type === 'ip_range'
            ? targetForm.scope_end
            : null,
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
      setShowAddTargetModal(false)

      setTargetForm({
        scope_type: 'single_device',
        identifier: '',
        address: '',
        scope_end: '',
        scope_cidr: '',
        credential_profile_id:
          created.credential_profile_id || '',
        platform_hint: 'cisco-iosxe',
        preferred_transport: 'netmiko',
      })
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to create target.',
      )
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
        throw new Error(
          'Profile name and secret reference are required.',
        )
      }

      const requiresUsername =
        profileForm.credential_type === 'ssh_password' ||
        profileForm.credential_type === 'ssh_key' ||
        profileForm.credential_type === 'snmp_v3'

      if (requiresUsername && !payload.username) {
        throw new Error(
          'Username is required for the selected credential type.',
        )
      }

      if (payload.transport_types.length === 0) {
        throw new Error('Select at least one supported transport.')
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
        err instanceof Error
          ? err.message
          : 'Unable to create credential profile.',
      )
    } finally {
      setCreatingProfile(false)
    }
  }

  async function handleTestSelectedProfile(profileId?: string) {
    const targetProfileId =
      profileId ||
      selectedTarget?.credential_profile_id ||
      targetForm.credential_profile_id ||
      profiles[0]?.profile_id

    if (!targetProfileId) {
      setError(
        'Select or create a credential profile before testing it.',
      )
      return
    }

    const profile =
      profiles.find((item) => item.profile_id === targetProfileId) ||
      null

    const transport = profile?.transport_types[0] || 'ssh'

    setTestingCredential(true)
    setError(null)

    try {
      const result = await testDiscoveryCredentialProfile(
        targetProfileId,
        {
          transport,
          target: selectedTarget?.address || 'test-target',
        },
      )

      setProfileTestResult(result)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to test the credential profile.',
      )
    } finally {
      setTestingCredential(false)
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
        requested_capabilities: {
          collector_name: 'cisco-ios-inventory',
        },
        metadata: {
          source: 'discovery-ui',
        },
        timeout_seconds: 120,
        correlation_id: crypto.randomUUID(),
      })

      setJob(created)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to start discovery.',
      )
    } finally {
      setStarting(false)
    }
  }

  const running = Boolean(job) && !terminalStates.has(job?.status || '')

  return (
    <div className="page discovery-page">
      <header className="discovery-header">
        <div className="discovery-header-main">
          <div className="discovery-eyebrow">NETWORK OPERATIONS</div>
          <h1>Network Discovery</h1>
          <p className="muted">
            Discover and validate managed network devices using
            configured credential profiles.
          </p>
        </div>

        <div className="discovery-header-actions">
          <button
            type="button"
            className="discovery-btn discovery-btn-icon"
            onClick={() =>
              void Promise.all([loadTargets(), loadProfiles()])
            }
            disabled={loading}
            title="Refresh"
            aria-label="Refresh"
          >
            ↻
          </button>
          <button
            type="button"
            className="discovery-btn discovery-btn-primary"
            disabled={
              !selectedTarget ||
              !selectedProfile ||
              starting ||
              running
            }
            onClick={() => void handleStartDiscovery()}
          >
            {starting
              ? 'Starting…'
              : running
                ? 'Running…'
                : 'Start discovery'}
          </button>
        </div>
      </header>

      <PageStatus job={job} starting={starting} />

      {error ? (
        <div className="discovery-error-banner" role="alert">
          <div>
            <strong>Operation failed</strong>
            <p>{error}</p>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      ) : null}

      <OverviewPanel
        targets={targets}
        selectedTarget={selectedTarget}
        profiles={profiles}
        job={job}
      />

      <div className="discovery-workspace">
        <TargetSidebar
          targets={targets}
          selectedTargetId={selectedTargetId}
          loading={loading}
          onSelect={(id) => {
            setSelectedTargetId(id)
            setProfileTestResult(null)
          }}
          onAddTarget={() => setShowAddTargetModal(true)}
        />

        <SelectedTargetPanel
          target={selectedTarget}
          profile={selectedProfile}
          profiles={profiles}
          profileTestResult={profileTestResult}
          testingCredential={testingCredential}
          onTestCredential={() =>
            void handleTestSelectedProfile(
              selectedProfile?.profile_id,
            )
          }
          onManageProfiles={() => setShowProfileComposer(true)}
        />
      </div>

      <DiscoveryExecutionPanel
        target={selectedTarget}
        job={job}
        starting={starting}
        onStartDiscovery={() => void handleStartDiscovery()}
      />

      <DiscoveryResultsPanel
        deviceResults={deviceResults}
        evidence={evidence}
      />

      {showAddTargetModal ? (
        <AddTargetModal
          form={targetForm}
          profiles={profiles}
          saving={savingTarget}
          onChange={(next) =>
            setTargetForm((current) => ({ ...current, ...next }))
          }
          onSubmit={handleCreateTarget}
          onCancel={() => setShowAddTargetModal(false)}
          onCreateProfile={() => {
            setShowAddTargetModal(false)
            setShowProfileComposer(true)
          }}
        />
      ) : null}

      {showProfileComposer ? (
        <CredentialProfileModal
          form={profileForm}
          creating={creatingProfile}
          onChange={(next) =>
            setProfileForm((current) => ({ ...current, ...next }))
          }
          onSubmit={handleCreateProfile}
          onCancel={() => setShowProfileComposer(false)}
        />
      ) : null}
    </div>
  )
}
