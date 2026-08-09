interface EmptyStateProps {
  title: string
  message: string
}

export function EmptyState({ title, message }: EmptyStateProps) {
  return (
    <div className="state-card" role="status" aria-live="polite">
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  )
}
