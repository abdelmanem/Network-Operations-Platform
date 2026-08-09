import axios, { type InternalAxiosRequestConfig } from 'axios'
import type {
  DashboardKpiSummaryResponse,
  DashboardTrendsResponseEnvelope,
  LoginRequest,
  TokenResponse,
  UserResponse,
} from '../types/api'

const api = axios.create({
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

function getErrorMessage(error: unknown): string {
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

export function normalizeApiError(error: unknown): string {
  return getErrorMessage(error)
}

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  try {
    const response = await api.post<TokenResponse>('/auth/login', credentials)
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getCurrentUser(): Promise<UserResponse> {
  try {
    const response = await api.get<UserResponse>('/auth/me')
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getDashboardKpis(): Promise<DashboardKpiSummaryResponse> {
  try {
    const response = await api.get<DashboardKpiSummaryResponse>(
      '/api/v1/dashboard/kpis',
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getDashboardAggregates(granularity = 'daily') {
  try {
    const response = await api.get(
      `/api/v1/dashboard/aggregates?granularity=${granularity}`,
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export async function getDashboardTrends(): Promise<DashboardTrendsResponseEnvelope> {
  try {
    const response = await api.get<DashboardTrendsResponseEnvelope>(
      '/api/v1/dashboard/trends',
    )
    return response.data
  } catch (error) {
    throw new Error(normalizeApiError(error))
  }
}

export default api
