interface DashboardSectionProps {
  title: string
  description?: string
  children: React.ReactNode
}

export function DashboardSection({ title, description, children }: DashboardSectionProps) {
  return (
    <section className="dashboard-section" aria-labelledby={`${title}-heading`}>
      <div className="section-header">
        <h2 id={`${title}-heading`}>{title}</h2>
        {description ? <p className="muted">{description}</p> : null}
      </div>
      {children}
    </section>
  )
}
