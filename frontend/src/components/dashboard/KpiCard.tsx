interface KpiCardProps {
  title: string
  value: string | number | null | undefined
  unit?: string | null
  description?: string | null
}

export function KpiCard({ title, value, unit, description }: KpiCardProps) {
  const hasValue = value !== null && value !== undefined && value !== ''
  const formattedValue = hasValue
    ? typeof value === 'number'
      ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(value)
      : value
    : 'Unavailable'

  return (
    <article className="card" aria-label={`${title} KPI`}>
      <div className="card-header">
        <h3>{title}</h3>
      </div>
      <p className="metric-value">
        {formattedValue}
        {unit ? <span className="metric-unit"> {unit}</span> : null}
      </p>
      {description ? <p className="muted">{description}</p> : null}
    </article>
  )
}
