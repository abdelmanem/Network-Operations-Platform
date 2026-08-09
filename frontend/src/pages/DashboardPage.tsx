import { useEffect, useState } from 'react'
import { StatusCard } from '../components/StatusCard'
import { getDashboardKpis, getDashboardTrends } from '../services/api'
import type {
  DashboardKpiSummaryResponse,
  DashboardTrendsResponseEnvelope,
} from '../types/api'

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardKpiSummaryResponse | null>(null)
  const [trends, setTrends] = useState<DashboardTrendsResponseEnvelope | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const [kpis, trendsResponse] = await Promise.all([
          getDashboardKpis(),
          getDashboardTrends(),
        ])
        setSummary(kpis)
        setTrends(trendsResponse)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load dashboard data')
      } finally {
        setIsLoading(false)
      }
    }

    void load()
  }, [])

  if (isLoading) {
    return <div className="loading-state">Loading dashboard…</div>
  }

  if (error) {
    return <div className="error-state">{error}</div>
  }

  return (
    <div>
      <h2>Dashboard</h2>
      <p className="muted">System status and module availability.</p>
      <div className="card-grid">
        <StatusCard title="Authentication" value="Connected" accent="success" />
        <StatusCard title="API" value="Connected" accent="success" />
        <StatusCard title="Frontend" value="Operational" accent="success" />
      </div>
      <div className="card-grid">
        <StatusCard title="Total devices" value={summary?.total_devices?.toString() ?? 'Unavailable'} />
        <StatusCard title="Discovery success" value={summary?.discovery_success_pct?.toString() ?? 'Unavailable'} />
        <StatusCard title="Findings" value={summary?.findings_total?.toString() ?? 'Unavailable'} />
      </div>
      <div className="card-grid">
        <StatusCard title="Trend snapshot" value={trends ? 'Available from backend contract' : 'Pending'} />
      </div>
    </div>
  )
}
