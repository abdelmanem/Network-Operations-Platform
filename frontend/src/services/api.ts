import axios, { type InternalAxiosRequestConfig } from 'axios'
import type {
  DashboardKpiSummaryResponse,
  DashboardTrendsResponseEnvelope,
  LoginRequest,
  TokenResponse,
  UserResponse,
} from '../types/api'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 10000,
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = window.localStorage.getItem('auth-token')
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>('/auth/login', credentials)
  return response.data
}

export async function getCurrentUser(): Promise<UserResponse> {
  const response = await api.get<UserResponse>('/auth/me')
  return response.data
}

export async function getDashboardKpis(): Promise<DashboardKpiSummaryResponse> {
  const response = await api.get<DashboardKpiSummaryResponse>('/dashboard/kpis')
  return response.data
}

export async function getDashboardAggregates(granularity = 'daily') {
  const response = await api.get(
    `/dashboard/aggregates?granularity=${granularity}`,
  )
  return response.data
}

export async function getDashboardTrends(): Promise<DashboardTrendsResponseEnvelope> {
  const response =
    await api.get<DashboardTrendsResponseEnvelope>('/dashboard/trends')
  return response.data
}

export default api
