import type { DashboardTrendEntryResponse } from '../../types/api'

interface TrendChartProps {
  title: string
  trend: DashboardTrendEntryResponse | null
}

function formatValue(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return 'n/a'
  }

  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(value)
}

export function TrendChart({ title, trend }: TrendChartProps) {
  if (!trend) {
    return null
  }

  const hasData = trend.baseline_value !== null || trend.current_value !== null

  return (
    <article className="card" aria-labelledby={`${title}-heading`}>
      <div className="card-header">
        <h3 id={`${title}-heading`}>{title}</h3>
        <span className="muted">{trend.direction}</span>
      </div>
      {hasData ? (
        <>
          <p className="metric-value">{formatValue(trend.current_value)}</p>
          <p className="muted">
            Baseline {formatValue(trend.baseline_value)} • {trend.trend}
          </p>
        </>
      ) : (
        <p className="muted">No trend data available.</p>
      )}
    </article>
  )
}
