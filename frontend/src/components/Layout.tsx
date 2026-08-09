import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const navItems = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/discovery', label: 'Discovery' },
  { to: '/compliance', label: 'Compliance' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/notifications', label: 'Notifications' },
  { to: '/audit', label: 'Audit' },
]

export function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <h1>Network Operations Platform</h1>
          <p className="muted">Production baseline frontend</p>
        </div>
        <nav>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }: { isActive: boolean }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <p>{user?.username ?? 'Signed out'}</p>
          <button type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="content">
        <header className="topbar">
          <Link to="/dashboard">Operations Console</Link>
          <span className="muted">Frontend foundation baseline</span>
        </header>
        <section className="page">
          <Outlet />
        </section>
      </main>
    </div>
  )
}
