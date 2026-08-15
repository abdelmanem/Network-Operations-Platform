import type { ReactElement } from 'react'
import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'
import { AuthProvider } from './lib/auth'
import { useAuth } from './hooks/useAuth'
import { AuditPage } from './pages/AuditPage'
import { CompliancePage } from './pages/CompliancePage'
import { DashboardPage } from './pages/DashboardPage'
import { DiscoveryPage } from './pages/DiscoveryPage'
import { JobsPage } from './pages/JobsPage'
import { LoginPage } from './pages/LoginPage'
import { NetworkPage } from './pages/NetworkPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { SettingsPage } from './pages/SettingsPage'

function ProtectedRoute({ children }: { children: ReactElement }) {
  const { isAuthenticated, status } = useAuth()

  if (status === 'loading') {
    return <div className="loading-state">Loading application…</div>
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return children
}

function createAppRouter() {
  return createBrowserRouter([
    {
      path: '/login',
      element: <LoginPage />,
    },
    {
      path: '/',
      element: (
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      ),
      errorElement: <ErrorBoundary> </ErrorBoundary>,
      children: [
        { index: true, element: <Navigate to="/dashboard" replace /> },
        { path: 'dashboard', element: <DashboardPage /> },
        { path: 'network', element: <NetworkPage /> },
        { path: 'discovery', element: <DiscoveryPage /> },
        { path: 'compliance', element: <CompliancePage /> },
        { path: 'jobs', element: <JobsPage /> },
        { path: 'notifications', element: <NotificationsPage /> },
        { path: 'audit', element: <AuditPage /> },
        { path: 'settings', element: <SettingsPage /> },
        { path: '*', element: <NotFoundPage /> },
      ],
    },
    { path: '*', element: <NotFoundPage /> },
  ])
}

function App() {
  const router = createAppRouter()

  return (
    <ErrorBoundary>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ErrorBoundary>
  )
}

export default App
