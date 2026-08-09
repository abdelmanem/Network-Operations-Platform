interface StatusPanelProps {
  title: string
  items: Array<{ label: string; value: string }>
}

export function StatusPanel({ title, items }: StatusPanelProps) {
  return (
    <section className="card" aria-labelledby={`${title}-heading`}>
      <div className="card-header">
        <h3 id={`${title}-heading`}>{title}</h3>
      </div>
      <ul className="status-list">
        {items.map((item) => (
          <li key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </li>
        ))}
      </ul>
    </section>
  )
}
