interface StatusCardProps {
  title: string
  value: string
  accent?: 'info' | 'warning' | 'success'
}

export function StatusCard({ title, value, accent = 'info' }: StatusCardProps) {
  return (
    <article className={`card ${accent}`}>
      <h3>{title}</h3>
      <p>{value}</p>
    </article>
  )
}
