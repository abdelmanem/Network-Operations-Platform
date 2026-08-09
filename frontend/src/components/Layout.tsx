import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { moduleRoutes } from '../routes/moduleRoutes'

function getPageTitle(pathname: string) {
  const match = moduleRoutes.find((route) => route.path === pathname)
  return match?.label ?? 'Platform'
}

export function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const title = getPageTitle(location.pathname)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <h1>Network Operations Platform</h1>
          <p className="muted">Frontend foundation baseline</p>
        </div>
        <nav aria-label="Primary navigation">
          {moduleRoutes.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
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
          <div>
            <Link to="/dashboard" className="topbar-link">
              Operations Console
            </Link>
            <p className="muted">{title}</p>
          </div>
          <span className="muted">Frontend foundation baseline</span>
        </header>
        <section className="page">
          <Outlet />
        </section>
      </main>
    </div>
  )
}
