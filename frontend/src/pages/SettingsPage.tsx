export function SettingsPage() {
  return (
    <div>
      <h2>Settings</h2>
      <p className="muted">Application configuration and frontend shell preferences.</p>
      <div className="card-grid">
        <article className="card">
          <h3>API base URL</h3>
          <p>{import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}</p>
        </article>
        <article className="card">
          <h3>Authentication</h3>
          <p>Bearer token stored in browser local storage.</p>
        </article>
      </div>
    </div>
  )
}
