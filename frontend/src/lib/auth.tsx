import {
  createContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { getCurrentUser, login as signIn } from '../services/api'
import type { UserResponse } from '../types/api'

interface AuthContextValue {
  user: UserResponse | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  status: 'loading' | 'ready'
}

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
)

function getStoredToken() {
  return window.localStorage.getItem('auth-token')
}

function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [hasStoredSession, setHasStoredSession] = useState<boolean>(Boolean(getStoredToken()))
  const [status, setStatus] = useState<'loading' | 'ready'>('loading')

  useEffect(() => {
    const restoreSession = async () => {
      const token = getStoredToken()
      if (!token) {
        setHasStoredSession(false)
        setStatus('ready')
        return
      }

      setHasStoredSession(true)
      try {
        const currentUser = await getCurrentUser()
        setUser(currentUser)
      } catch {
        window.localStorage.removeItem('auth-token')
        setHasStoredSession(false)
        setUser(null)
      } finally {
        setStatus('ready')
      }
    }

    void restoreSession()
  }, [])

  const login = async (username: string, password: string) => {
    setStatus('loading')
    const tokenResponse = await signIn({ username, password })
    window.localStorage.setItem('auth-token', tokenResponse.access_token)
    setHasStoredSession(true)
    const currentUser = await getCurrentUser()
    setUser(currentUser)
    setStatus('ready')
  }

  const logout = () => {
    window.localStorage.removeItem('auth-token')
    setHasStoredSession(false)
    setUser(null)
    setStatus('ready')
  }

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user) || hasStoredSession,
      login,
      logout,
      status,
    }),
    [user, hasStoredSession, status],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export { AuthProvider }
