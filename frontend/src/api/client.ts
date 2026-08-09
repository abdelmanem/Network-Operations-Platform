import axios, { type InternalAxiosRequestConfig } from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000,
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = window.localStorage.getItem('auth-token')
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      window.localStorage.removeItem('auth-token')
    }
    return Promise.reject(error)
  },
)

export function normalizeApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    if (status === 401) {
      return 'Authentication failed. Please sign in again.'
    }
    if (status === 403) {
      return 'You do not have permission to view this resource.'
    }
    if (status === 404) {
      return 'The requested resource could not be found.'
    }
    if (status && status >= 500) {
      return 'The server could not process the request. Please try again later.'
    }
    if (error.code === 'ERR_NETWORK') {
      return 'The backend is unavailable. Please try again shortly.'
    }
    return error.response?.data?.detail || 'The request could not be completed.'
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'The request could not be completed.'
}
