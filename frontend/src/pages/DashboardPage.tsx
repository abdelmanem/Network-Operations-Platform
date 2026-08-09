import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../components/dashboard/EmptyState'
import { ErrorState } from '../components/dashboard/ErrorState'
import { DashboardSection } from '../components/dashboard/DashboardSection'
import { KpiCard } from '../components/dashboard/KpiCard'
import { StatusPanel } from '../components/dashboard/StatusPanel'
import { TrendChart } from '../components/dashboard/TrendChart'
import { getDashboardKpis, getDashboardTrends } from '../api/dashboard'
import type {
  DashboardKpiSummaryResponse,
  DashboardTrendsResponseEnvelope,
} from '../types/api'

type DashboardLoadState = 'loading' | 'ready' | 'empty' | 'error'

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardKpiSummaryResponse | null>(null)
  const [trends, setTrends] = useState<DashboardTrendsResponseEnvelope | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadState, setLoadState] = useState<DashboardLoadState>('loading')

  const loadDashboardData = useCallback(async () => {
    setLoadState('loading')
    setError(null)

    try {
      const [kpis, trendsResponse] = await Promise.all([
        getDashboardKpis(),
        getDashboardTrends(),
      ])

      const hasOperationalData = Boolean(
        kpis.total_devices !== null ||
          kpis.reachable_devices !== null ||
          kpis.unreachable_devices !== null ||
          kpis.discovery_success_pct !== null ||
          kpis.netbox_accuracy_pct !== null ||
          kpis.missing_devices !== null ||
          kpis.extra_devices !== null ||
          kpis.modified_devices !== null ||
          kpis.findings_total !== null ||
          kpis.critical_findings !== null ||
          kpis.major_findings !== null ||
          kpis.minor_findings !== null ||
          Object.values(trendsResponse.trends).some(
            (entry) => entry.current_value !== null || entry.baseline_value !== null,
          ),
      )

      setSummary(kpis)
      setTrends(trendsResponse)
      setLoadState(hasOperationalData ? 'ready' : 'empty')
    } catch (err) {
      setSummary(null)
      setTrends(null)
      setLoadState('error')
      setError(err instanceof Error ? err.message : 'Unable to load dashboard data')
    }
  }, [])

  useEffect(() => {
    void loadDashboardData()
  }, [loadDashboardData])

  const kpiCards = useMemo(() => {
    const cards = [
      {
        title: 'Total devices',
        value: summary?.total_devices,
        unit: null,
        description: 'Current device inventory footprint',
      },
      {
        title: 'Discovery success',
        value: summary?.discovery_success_pct,
        unit: '%',
        description: 'Recent discovery success rate',
      },
      {
        title: 'Findings total',
        value: summary?.findings_total,
        unit: null,
        description: 'Open findings across the platform',
      },
      {
        title: 'Reachable devices',
        value: summary?.reachable_devices,
        unit: null,
        description: 'Devices reachable from the current inventory view',
      },
    ]

    return cards
  }, [summary])

  if (loadState === 'loading') {
    return (
      <div className="state-card" role="status" aria-live="polite">
        <h2>Operations Dashboard</h2>
        <p>Loading dashboard data…</p>
      </div>
    )
  }

  if (loadState === 'error') {
    return <ErrorState message={error ?? 'Unable to load dashboard data.'} onRetry={loadDashboardData} />
  }

  if (loadState === 'empty') {
    return <EmptyState title="No operational data" message="No operational data is currently available." />
  }

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div>
          <h2>Operations Dashboard</h2>
          <p className="muted">Real-time view of the current platform health and operational activity.</p>
        </div>
      </header>

      <DashboardSection title="Key performance indicators" description="Values are sourced from the backend KPI summary contract.">
        <div className="card-grid">
          {kpiCards.map((card) => (
            <KpiCard
              key={card.title}
              title={card.title}
              value={card.value}
              unit={card.unit}
              description={card.description}
            />
          ))}
        </div>
      </DashboardSection>

      <DashboardSection title="Operational trends" description="Trend snapshots returned by the dashboard trends API.">
        <div className="card-grid">
          <TrendChart title="Discovery success" trend={trends?.trends.discovery_success_trend ?? null} />
          <TrendChart title="Device count" trend={trends?.trends.device_count_trend ?? null} />
          <TrendChart title="Findings count" trend={trends?.trends.findings_count_trend ?? null} />
          <TrendChart title="Drift" trend={trends?.trends.drift_trend ?? null} />
        </div>
      </DashboardSection>

      <DashboardSection title="Platform status" description="Operational status derived from backend dashboard data.">
        <div className="card-grid">
          <StatusPanel
            title="Platform operational status"
            items={[
              { label: 'Latest run', value: summary?.latest_run_id ?? 'Unavailable' },
              { label: 'Started at', value: summary?.latest_run_started_at ?? 'Unavailable' },
              { label: 'Finished at', value: summary?.latest_run_finished_at ?? 'Unavailable' },
            ]}
          />
          <StatusPanel
            title="Frontend status"
            items={[
              { label: 'Navigation', value: 'Operational' },
              { label: 'Dashboard view', value: 'Available' },
              { label: 'Module links', value: 'Ready' },
            ]}
          />
        </div>
      </DashboardSection>

      <DashboardSection title="Quick navigation" description="Use these module links to move across the platform without entering operational workflows.">
        <div className="card-grid">
          <Link className="nav-card" to="/discovery">
            Discovery
            <span>View Discovery</span>
          </Link>
          <Link className="nav-card" to="/jobs">
            Jobs
            <span>View Jobs</span>
          </Link>
          <Link className="nav-card" to="/compliance">
            Compliance
            <span>View Compliance</span>
          </Link>
          <Link className="nav-card" to="/notifications">
            Notifications
            <span>View Notifications</span>
          </Link>
        </div>
      </DashboardSection>
    </div>
  )
}
