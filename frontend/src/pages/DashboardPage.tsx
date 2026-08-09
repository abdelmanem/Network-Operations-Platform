import { useEffect, useState } from 'react'
import { getDashboardKpis, getDashboardTrends } from '../services/api'
import type {
  DashboardKpiSummaryResponse,
  DashboardTrendsResponseEnvelope,
} from '../types/api'

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardKpiSummaryResponse | null>(
    null,
  )
  const [trends, setTrends] = useState<DashboardTrendsResponseEnvelope | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [kpis, trendsResponse] = await Promise.all([
          getDashboardKpis(),
          getDashboardTrends(),
        ])
        setSummary(kpis)
        setTrends(trendsResponse)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Unable to load dashboard data',
        )
      }
    }

    void load()
  }, [])

  if (error) {
    return <div className="error-state">{error}</div>
  }

  return (
    <div>
      <h2>Dashboard</h2>
      <p className="muted">Backend dashboard contract placeholder.</p>
      <div className="card-grid">
        <article className="card">
          <h3>Total devices</h3>
          <p>{summary?.total_devices ?? 'Unavailable'}</p>
        </article>
        <article className="card">
          <h3>Discovery success</h3>
          <p>{summary?.discovery_success_pct ?? 'Unavailable'}</p>
        </article>
        <article className="card">
          <h3>Findings</h3>
          <p>{summary?.findings_total ?? 'Unavailable'}</p>
        </article>
      </div>
      <div className="card-grid">
        <article className="card">
          <h3>Trend snapshot</h3>
          <p>{trends ? 'Available from backend contract' : 'Pending'}</p>
        </article>
      </div>
    </div>
  )
}
